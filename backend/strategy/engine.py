import asyncio
import logging
from datetime import datetime, time, date
from typing import Optional, Dict
from dataclasses import dataclass, field

from .supertrend import SupertrendCalculator, Candle, SupertrendResult
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class CandleBuffer:
    """Accumulates tick data into 3-minute candles."""
    current_open: Optional[float] = None
    current_high: float = 0
    current_low: float = float("inf")
    current_close: float = 0
    current_volume: float = 0
    candle_start: Optional[datetime] = None
    CANDLE_MINUTES: int = 3

    def update_tick(self, price: float, volume: float = 0, ts: datetime = None) -> Optional[Candle]:
        """Returns closed candle if 3-min boundary crossed."""
        ts = ts or datetime.now()
        
        if self.candle_start is None:
            # Align to 3-minute boundary
            minute = ts.minute - (ts.minute % self.CANDLE_MINUTES)
            self.candle_start = ts.replace(minute=minute, second=0, microsecond=0)
            self.current_open = price

        elapsed = (ts - self.candle_start).total_seconds() / 60
        
        if elapsed >= self.CANDLE_MINUTES:
            # Close current candle
            closed = Candle(
                timestamp=self.candle_start,
                open=self.current_open or price,
                high=self.current_high,
                low=self.current_low if self.current_low != float("inf") else price,
                close=self.current_close or price,
                volume=self.current_volume
            )
            # Start new candle
            minute = ts.minute - (ts.minute % self.CANDLE_MINUTES)
            self.candle_start = ts.replace(minute=minute, second=0, microsecond=0)
            self.current_open = price
            self.current_high = price
            self.current_low = price
            self.current_close = price
            self.current_volume = volume
            return closed

        # Update current candle
        if self.current_open is None:
            self.current_open = price
        self.current_high = max(self.current_high, price)
        self.current_low = min(self.current_low, price)
        self.current_close = price
        self.current_volume += volume
        return None


@dataclass
class LegState:
    leg: str  # CE or PE
    symbol: str = ""
    reentry_count: int = 0
    is_stopped: bool = False
    open_trade_id: Optional[int] = None
    open_qty: int = 0
    entry_price: float = 0.0
    candle_buffer: CandleBuffer = field(default_factory=CandleBuffer)
    st_calculator: SupertrendCalculator = field(default_factory=lambda: SupertrendCalculator(
        settings.ST_PERIOD, settings.ST_MULTIPLIER
    ))
    last_st_result: Optional[SupertrendResult] = None
    last_signal_time: Optional[datetime] = None

    def get_qty_for_reentry(self, lot_size: int) -> int:
        """1X, 2X, 3X based on reentry count."""
        multiplier = min(self.reentry_count + 1, 3)
        return lot_size * multiplier


class StrategyEngine:
    """Core strategy logic. Decoupled from order execution for testability."""

    def __init__(self, lot_size: int = 50, scaling_enabled: bool = True,
                 max_daily_loss: float = 10000, max_trades: int = 20):
        self.lot_size = lot_size
        self.scaling_enabled = scaling_enabled
        self.max_daily_loss = max_daily_loss
        self.max_trades = max_trades
        
        self.ce = LegState("CE")
        self.pe = LegState("PE")
        
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.is_halted = False
        
        self._callbacks: Dict[str, list] = {
            "on_entry": [],
            "on_exit": [],
            "on_sl": [],
            "on_reentry": []
        }

    def on(self, event: str, callback):
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    async def _emit(self, event: str, **kwargs):
        for cb in self._callbacks.get(event, []):
            try:
                await cb(**kwargs)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def _get_leg(self, leg: str) -> LegState:
        return self.ce if leg == "CE" else self.pe

    def is_entry_allowed(self) -> bool:
        now = datetime.now().time()
        last_entry = time(14, 45)
        market_open = time(9, 15)
        if not (market_open <= now <= last_entry):
            return False
        if self.is_halted:
            return False
        if self.daily_pnl <= -abs(self.max_daily_loss):
            logger.warning("Max daily loss reached, halting.")
            self.is_halted = True
            return False
        if self.daily_trades >= self.max_trades:
            logger.warning("Max trades reached.")
            return False
        return True

    def is_force_exit_time(self) -> bool:
        now = datetime.now().time()
        return now >= time(15, 15)

    async def process_tick(self, leg: str, price: float, volume: float = 0) -> Optional[dict]:
        """
        Process a live tick for CE or PE.
        Returns action dict if an order should be placed.
        """
        ls = self._get_leg(leg)
        ts = datetime.now()
        
        # Update candle buffer
        closed_candle = ls.candle_buffer.update_tick(price, volume, ts)
        
        if closed_candle is None:
            return None  # No closed candle yet

        # Feed to supertrend
        st_result = ls.st_calculator.add_candle(closed_candle)
        if st_result is None:
            return None  # Not enough data

        ls.last_st_result = st_result
        
        # Force exit check
        if self.is_force_exit_time():
            if ls.open_trade_id is not None:
                return {
                    "action": "EXIT",
                    "leg": leg,
                    "reason": "FORCE",
                    "price": price,
                    "trade_id": ls.open_trade_id,
                    "qty": ls.open_qty
                }
            return None

        # Check for SL (price closes above ST when we're short)
        if ls.open_trade_id is not None:
            if closed_candle.close > st_result.value:
                # SL triggered
                return {
                    "action": "EXIT",
                    "leg": leg,
                    "reason": "SL",
                    "price": price,
                    "trade_id": ls.open_trade_id,
                    "qty": ls.open_qty
                }

        # Entry signal: candle closes BELOW supertrend
        if ls.open_trade_id is None and closed_candle.close < st_result.value:
            if ls.is_stopped:
                return None
            if not self.is_entry_allowed():
                return None
            
            qty = ls.get_qty_for_reentry(self.lot_size) if self.scaling_enabled else self.lot_size
            ls.last_signal_time = ts
            
            return {
                "action": "ENTRY",
                "leg": leg,
                "price": price,
                "qty": qty,
                "reentry_count": ls.reentry_count,
                "st_value": st_result.value
            }

        return None

    async def on_order_filled(self, leg: str, action: str, trade_id: int,
                               qty: int, fill_price: float):
        ls = self._get_leg(leg)
        if action == "ENTRY":
            ls.open_trade_id = trade_id
            ls.open_qty = qty
            ls.entry_price = fill_price
            self.daily_trades += 1
        elif action == "EXIT":
            pnl = (ls.entry_price - fill_price) * ls.open_qty
            self.daily_pnl += pnl
            ls.open_trade_id = None
            ls.open_qty = 0
            ls.entry_price = 0.0

    async def on_sl_hit(self, leg: str):
        ls = self._get_leg(leg)
        ls.reentry_count += 1
        if ls.reentry_count >= 3:
            ls.is_stopped = True
            logger.warning(f"{leg}: Max reentries reached. Stopping leg.")

    def get_supertrend_info(self, leg: str) -> dict:
        ls = self._get_leg(leg)
        if not ls.last_st_result:
            return {"direction": "unknown", "value": 0, "signal_time": None, "distance": 0}
        return {
            "direction": ls.last_st_result.direction,
            "value": ls.last_st_result.value,
            "signal_time": ls.last_st_result.timestamp.isoformat() if ls.last_st_result.timestamp else None,
            "distance": round(abs(ls.candle_buffer.current_close - ls.last_st_result.value), 2)
        }

    def reset_day(self):
        self.ce = LegState("CE")
        self.pe = LegState("PE")
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.is_halted = False

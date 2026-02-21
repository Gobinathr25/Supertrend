import asyncio
import logging
from datetime import datetime, time, date
from typing import Optional

from .fyers_service import FyersService, ATMCalculator
from .order_service import OrderService
from strategy.engine import StrategyEngine
from telegram.service import TelegramService
from database.models import AsyncSessionLocal
from database.operations import TradeRepo, DailyPnLRepo, LogRepo

logger = logging.getLogger(__name__)


class PaperOrderService:
    """Simulates order execution locally. No real orders sent."""

    def __init__(self, lot_size=50):
        self.lot_size = lot_size
        self._trade_price_cache = {}

    async def sell_option(self, symbol, leg, qty, reentry_count=0):
        from database.models import AsyncSessionLocal
        from database.operations import TradeRepo, LogRepo
        from datetime import datetime
        # Use last known LTP as fill price
        fill_price = self._trade_price_cache.get(symbol, 100.0)
        async with AsyncSessionLocal() as db:
            repo = TradeRepo(db)
            trade = await repo.create(
                symbol=symbol, leg=leg, entry_time=datetime.now(),
                qty=qty, entry_price=fill_price,
                reentry_count=reentry_count,
                order_id="PAPER", fyers_order_id="PAPER", status="OPEN"
            )
            await LogRepo(db).log("INFO", f"[PAPER] {leg} ENTRY",
                                  {"symbol": symbol, "qty": qty, "price": fill_price})
        return {"trade_id": trade.id, "fill_price": fill_price, "order_id": "PAPER"}

    async def exit_option(self, trade_id, symbol, leg, qty, exit_reason):
        from database.models import AsyncSessionLocal
        from database.operations import TradeRepo, DailyPnLRepo, LogRepo
        fill_price = self._trade_price_cache.get(symbol, 100.0)
        async with AsyncSessionLocal() as db:
            repo  = TradeRepo(db)
            trade = await repo.close_trade(trade_id, fill_price, exit_reason)
            pnl   = trade.pnl if trade else 0
            result = "WIN" if pnl >= 0 else "LOSS"
            await DailyPnLRepo(db).upsert_today(pnl, result)
            await LogRepo(db).log("INFO", f"[PAPER] {leg} EXIT",
                                  {"symbol": symbol, "price": fill_price, "pnl": pnl})
        return {"fill_price": fill_price, "pnl": pnl}

    def update_price(self, symbol, price):
        self._trade_price_cache[symbol] = price

    async def force_exit_all(self, open_trades):
        results = []
        for t in open_trades:
            r = await self.exit_option(t.id, t.symbol, t.leg, t.qty, "FORCE")
            results.append(r)
        return results


class TradingOrchestrator:
    def __init__(self):
        self.fyers      = FyersService()
        self.telegram   = TelegramService()
        self.strategy: Optional[StrategyEngine] = None
        self.order_svc  = None
        self.atm_calc   = ATMCalculator()

        # Market data
        self.nifty_spot   = 0.0
        self.sensex_spot  = 0.0
        self.atm_strike   = 0
        self.sensex_atm   = 0
        self.ce_symbol    = ""
        self.pe_symbol    = ""
        self.sensex_ce_symbol = ""
        self.sensex_pe_symbol = ""
        self.ce_ltp       = 0.0
        self.pe_ltp       = 0.0
        self.sensex_ce_ltp = 0.0
        self.sensex_pe_ltp = 0.0
        self.available_margin = 0.0
        self.used_margin      = 0.0

        # Config
        self.trade_mode     = "real"   # "real" or "paper"
        self.nifty_enabled  = True
        self.sensex_enabled = False
        self.is_running     = False
        self._daily_summary_sent = False
        self._initialized   = False

    def configure(self, client_id, secret_key, access_token,
                  telegram_token="", telegram_chat="",
                  lot_size=50, max_daily_loss=10000, max_trades=20,
                  scaling=True, trade_mode="real",
                  nifty_enabled=True, sensex_enabled=False):

        self.trade_mode     = trade_mode
        self.nifty_enabled  = nifty_enabled
        self.sensex_enabled = sensex_enabled

        self.fyers.configure(client_id, secret_key, access_token)
        self.telegram.configure(telegram_token, telegram_chat)

        self.strategy = StrategyEngine(
            lot_size=lot_size, scaling_enabled=scaling,
            max_daily_loss=max_daily_loss, max_trades=max_trades
        )

        if trade_mode == "paper":
            self.order_svc = PaperOrderService(lot_size)
        else:
            self.order_svc = OrderService(self.fyers, lot_size)

        self._initialized = True

    async def initialize(self):
        if not self._initialized:
            return False

        # Both real AND paper mode fetch live data from Fyers.
        # Paper mode only differs at order execution time — NOT at data fetching.
        try:
            funds = await self.fyers.get_funds()
            if funds.get("s") == "ok":
                for item in funds.get("fund_limit", []):
                    t = item.get("title", "")
                    if t == "Available Balance": self.available_margin = item.get("equityAmount", 0)
                    elif t == "Utilized Amount": self.used_margin      = item.get("equityAmount", 0)

            quotes = await self.fyers.get_quotes(["NSE:NIFTY50-INDEX", "BSE:SENSEX-INDEX"])
            if quotes.get("s") == "ok":
                for q in quotes.get("d", []):
                    sym = q.get("v", {}).get("short_name", "")
                    ltp = q.get("v", {}).get("lp", 0)
                    if "NIFTY" in sym:  self.nifty_spot  = ltp
                    elif "SENSEX" in sym: self.sensex_spot = ltp

            expiry = self.atm_calc.get_nearest_expiry_str()
            self.atm_strike = self.atm_calc.get_atm_strike(self.nifty_spot)
            self.sensex_atm = self.atm_calc.get_atm_strike(self.sensex_spot, step=100)
            self.ce_symbol  = self.atm_calc.get_option_symbol("NIFTY",  self.atm_strike, expiry, "CE")
            self.pe_symbol  = self.atm_calc.get_option_symbol("NIFTY",  self.atm_strike, expiry, "PE")
            self.sensex_ce_symbol = self.atm_calc.get_option_symbol("SENSEX", self.sensex_atm, expiry, "CE")
            self.sensex_pe_symbol = self.atm_calc.get_option_symbol("SENSEX", self.sensex_atm, expiry, "PE")
            logger.info(f"NIFTY ATM={self.atm_strike} SENSEX ATM={self.sensex_atm}")
            return True
        except Exception as e:
            logger.error(f"Init error: {e}")
            return False

    async def on_ws_data(self, data: dict):
        try:
            symbol = data.get("symbol", "")
            ltp    = data.get("ltp", data.get("lp", 0))
            volume = data.get("vol_traded_today", 0)

            if symbol == "NSE:NIFTY50-INDEX":
                self.nifty_spot = ltp
            elif symbol == "BSE:SENSEX-INDEX":
                self.sensex_spot = ltp
            elif symbol == self.ce_symbol and self.nifty_enabled:
                self.ce_ltp = ltp
                if self.trade_mode == "paper" and hasattr(self.order_svc, 'update_price'):
                    self.order_svc.update_price(symbol, ltp)
                await self._process_leg("NIFTY", "CE", ltp, volume)
            elif symbol == self.pe_symbol and self.nifty_enabled:
                self.pe_ltp = ltp
                if self.trade_mode == "paper" and hasattr(self.order_svc, 'update_price'):
                    self.order_svc.update_price(symbol, ltp)
                await self._process_leg("NIFTY", "PE", ltp, volume)
            elif symbol == self.sensex_ce_symbol and self.sensex_enabled:
                self.sensex_ce_ltp = ltp
                if self.trade_mode == "paper" and hasattr(self.order_svc, 'update_price'):
                    self.order_svc.update_price(symbol, ltp)
                await self._process_leg("SENSEX", "CE", ltp, volume)
            elif symbol == self.sensex_pe_symbol and self.sensex_enabled:
                self.sensex_pe_ltp = ltp
                if self.trade_mode == "paper" and hasattr(self.order_svc, 'update_price'):
                    self.order_svc.update_price(symbol, ltp)
                await self._process_leg("SENSEX", "PE", ltp, volume)
        except Exception as e:
            logger.error(f"WS data error: {e}")

    async def _process_leg(self, index: str, leg: str, price: float, volume: float):
        if not self.strategy or not self.order_svc:
            return

        # Use combined key for SENSEX legs
        st_leg = f"{index}_{leg}" if index == "SENSEX" else leg
        symbol = (self.sensex_ce_symbol if index == "SENSEX" and leg == "CE"
                  else self.sensex_pe_symbol if index == "SENSEX" and leg == "PE"
                  else self.ce_symbol if leg == "CE" else self.pe_symbol)

        action = await self.strategy.process_tick(leg, price, volume)
        if not action:
            return

        if action["action"] == "ENTRY":
            result = await self.order_svc.sell_option(
                symbol=symbol, leg=leg, qty=action["qty"],
                reentry_count=action["reentry_count"]
            )
            if result:
                await self.strategy.on_order_filled(leg, "ENTRY", result["trade_id"],
                                                    action["qty"], result["fill_price"])
                mode_tag = "[PAPER] " if self.trade_mode == "paper" else ""
                await self.telegram.notify_entry(symbol, action["qty"], result["fill_price"], leg)

        elif action["action"] == "EXIT":
            result = await self.order_svc.exit_option(
                trade_id=action["trade_id"], symbol=symbol, leg=leg,
                qty=action["qty"], exit_reason=action["reason"]
            )
            if result:
                await self.strategy.on_order_filled(leg, "EXIT", action["trade_id"],
                                                    action["qty"], result["fill_price"])
                if action["reason"] == "SL":
                    await self.strategy.on_sl_hit(leg)
                    await self.telegram.notify_sl(symbol, result["fill_price"], result["pnl"], leg)
                else:
                    await self.telegram.notify_exit(symbol, action["qty"], result["fill_price"],
                                                    result["pnl"], action["reason"], leg)

    async def check_force_exit(self):
        now = datetime.now().time()
        if now >= time(15, 15) and not self._daily_summary_sent:
            async with AsyncSessionLocal() as db:
                trades = await TradeRepo(db).get_open_trades()
                if trades:
                    await self.order_svc.force_exit_all(trades)
            await self._send_daily_summary()
            self._daily_summary_sent = True

    async def _send_daily_summary(self):
        async with AsyncSessionLocal() as db:
            records = await DailyPnLRepo(db).get_all()
            if records:
                r = records[0]
                await self.telegram.send_daily_summary(
                    r.total_pnl, r.total_trades, r.winning_trades, r.losing_trades)

    async def _refresh_margin(self):
        if self.trade_mode == "paper":
            return
        try:
            funds = await self.fyers.get_funds()
            if funds.get("s") == "ok":
                for item in funds.get("fund_limit", []):
                    t = item.get("title", "")
                    if t == "Available Balance": self.available_margin = item.get("equityAmount", 0)
                    elif t == "Utilized Amount": self.used_margin      = item.get("equityAmount", 0)
        except Exception:
            pass

    async def start(self):
        if not self._initialized:
            return
        self.is_running = True
        self._daily_summary_sent = False
        self.strategy.reset_day()

        symbols = ["NSE:NIFTY50-INDEX", "BSE:SENSEX-INDEX"]
        if self.nifty_enabled:
            symbols += [self.ce_symbol, self.pe_symbol]
        if self.sensex_enabled:
            symbols += [self.sensex_ce_symbol, self.sensex_pe_symbol]

        self.fyers.add_ws_callback(self.on_ws_data)
        await asyncio.gather(
            self.fyers.start_websocket(symbols),
            self._scheduler()
        )

    async def _scheduler(self):
        while self.is_running:
            await self.check_force_exit()
            await self._refresh_margin()
            await asyncio.sleep(30)

    def stop(self):
        self.is_running = False
        self.fyers.stop_websocket()

    def get_status(self) -> dict:
        ce_st = self.strategy.get_supertrend_info("CE") if self.strategy else {}
        pe_st = self.strategy.get_supertrend_info("PE") if self.strategy else {}
        return {
            "nifty_spot":      self.nifty_spot,
            "sensex_spot":     self.sensex_spot,
            "atm_strike":      self.atm_strike,
            "sensex_atm":      self.sensex_atm,
            "ce_symbol":       self.ce_symbol,
            "pe_symbol":       self.pe_symbol,
            "sensex_ce_symbol": self.sensex_ce_symbol,
            "sensex_pe_symbol": self.sensex_pe_symbol,
            "ce_ltp":          self.ce_ltp,
            "pe_ltp":          self.pe_ltp,
            "sensex_ce_ltp":   self.sensex_ce_ltp,
            "sensex_pe_ltp":   self.sensex_pe_ltp,
            "available_margin": self.available_margin,
            "used_margin":      self.used_margin,
            "daily_pnl":       self.strategy.daily_pnl if self.strategy else 0,
            "daily_trades":    self.strategy.daily_trades if self.strategy else 0,
            "is_halted":       self.strategy.is_halted if self.strategy else False,
            "ce_supertrend":   ce_st,
            "pe_supertrend":   pe_st,
            "is_running":      self.is_running,
            "trade_mode":      self.trade_mode,
            "nifty_enabled":   self.nifty_enabled,
            "sensex_enabled":  self.sensex_enabled,
        }


orchestrator = TradingOrchestrator()

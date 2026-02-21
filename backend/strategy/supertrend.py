import numpy as np
import pandas as pd
from typing import Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0


@dataclass
class SupertrendResult:
    value: float
    direction: str  # "bullish" or "bearish"
    signal: Optional[str]  # "BUY", "SELL", or None
    timestamp: datetime


class SupertrendCalculator:
    """
    Supertrend indicator calculator.
    Period: 10, Multiplier: 3 (configurable)
    Direction:
      - bearish (price below ST) → SELL signal
      - bullish (price above ST) → no signal / exit
    """

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier
        self.candles: list[Candle] = []
        self._last_direction = None
        self._last_signal = None

    def add_candle(self, candle: Candle) -> Optional[SupertrendResult]:
        """Add a closed candle and recalculate. Returns result if enough data."""
        self.candles.append(candle)
        if len(self.candles) < self.period + 1:
            return None
        return self._calculate()

    def _calculate(self) -> SupertrendResult:
        df = pd.DataFrame([
            {"high": c.high, "low": c.low, "close": c.close, "ts": c.timestamp}
            for c in self.candles
        ])

        # ATR
        df["prev_close"] = df["close"].shift(1)
        df["tr"] = df[["high", "low", "prev_close"]].apply(
            lambda r: max(
                r["high"] - r["low"],
                abs(r["high"] - r["prev_close"]) if pd.notna(r["prev_close"]) else 0,
                abs(r["low"] - r["prev_close"]) if pd.notna(r["prev_close"]) else 0
            ), axis=1
        )
        df["atr"] = df["tr"].ewm(span=self.period, adjust=False).mean()

        # Basic bands
        df["hl2"] = (df["high"] + df["low"]) / 2
        df["upper_band"] = df["hl2"] + self.multiplier * df["atr"]
        df["lower_band"] = df["hl2"] - self.multiplier * df["atr"]

        # Supertrend
        supertrend = np.zeros(len(df))
        direction = np.zeros(len(df))  # 1 = bullish, -1 = bearish

        upper = df["upper_band"].values
        lower = df["lower_band"].values
        close = df["close"].values

        for i in range(1, len(df)):
            # Adjust bands
            if lower[i] > lower[i-1] or close[i-1] < lower[i-1]:
                lower[i] = lower[i]
            else:
                lower[i] = lower[i-1]

            if upper[i] < upper[i-1] or close[i-1] > upper[i-1]:
                upper[i] = upper[i]
            else:
                upper[i] = upper[i-1]

            if supertrend[i-1] == upper[i-1]:
                if close[i] <= upper[i]:
                    supertrend[i] = upper[i]
                    direction[i] = -1
                else:
                    supertrend[i] = lower[i]
                    direction[i] = 1
            else:
                if close[i] >= lower[i]:
                    supertrend[i] = lower[i]
                    direction[i] = 1
                else:
                    supertrend[i] = upper[i]
                    direction[i] = -1

        # Initialize first
        if direction[1] == 0:
            direction[1] = 1 if close[1] >= lower[1] else -1
            supertrend[1] = lower[1] if direction[1] == 1 else upper[1]

        last_dir = direction[-1]
        last_st = supertrend[-1]
        prev_dir = direction[-2] if len(direction) > 1 else last_dir

        dir_str = "bullish" if last_dir == 1 else "bearish"
        
        # Signal on direction change
        signal = None
        if last_dir != prev_dir:
            if last_dir == -1:
                signal = "SELL"
            else:
                signal = "EXIT"

        return SupertrendResult(
            value=round(last_st, 2),
            direction=dir_str,
            signal=signal,
            timestamp=self.candles[-1].timestamp
        )

    def get_current(self) -> Optional[SupertrendResult]:
        if len(self.candles) < self.period + 1:
            return None
        return self._calculate()

    def reset(self):
        self.candles = []
        self._last_direction = None
        self._last_signal = None

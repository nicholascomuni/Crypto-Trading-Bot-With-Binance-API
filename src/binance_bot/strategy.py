"""Strategy interface and an example SMA crossover strategy."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from binance_bot.models import Candle


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class Signal:
    """A trading intention emitted by a strategy. Nothing is executed on the exchange."""

    strategy: str
    symbol: str
    side: Side
    price: Decimal
    time: datetime
    reason: str = ""


@runtime_checkable
class Strategy(Protocol):
    """Anything with a ``name`` and an ``on_candle`` hook can be plugged into the engine.

    ``on_candle`` receives closed candles in chronological order for every subscribed
    symbol, so implementations should keep per-symbol state.
    """

    name: str

    def on_candle(self, candle: Candle) -> Signal | None: ...


class SmaCrossStrategy:
    """Emit BUY when the fast SMA crosses above the slow SMA and SELL when it crosses below.

    No signal is produced until ``slow`` candles have been seen for a symbol, and the
    first fully-formed state only sets the baseline, so warm-up never triggers a trade.
    """

    def __init__(self, fast: int = 9, slow: int = 21) -> None:
        if not 0 < fast < slow:
            raise ValueError("Require 0 < fast < slow")
        self.fast = fast
        self.slow = slow
        self.name = f"sma_cross_{fast}_{slow}"
        self._closes: dict[str, deque[Decimal]] = {}
        self._fast_above: dict[str, bool] = {}

    def warm_up(self, candles: Iterable[Candle]) -> None:
        """Feed historical candles to build state, discarding any signals."""
        for candle in candles:
            self.on_candle(candle)

    def on_candle(self, candle: Candle) -> Signal | None:
        key = f"{candle.symbol}:{candle.interval}"
        closes = self._closes.setdefault(key, deque(maxlen=self.slow))
        closes.append(candle.close)
        if len(closes) < self.slow:
            return None

        fast_sma = sum(list(closes)[-self.fast :], Decimal(0)) / self.fast
        slow_sma = sum(closes, Decimal(0)) / self.slow
        if fast_sma == slow_sma:
            return None  # no strict ordering; keep the previous regime

        fast_above = fast_sma > slow_sma
        previous = self._fast_above.get(key)
        self._fast_above[key] = fast_above
        if previous is None or previous == fast_above:
            return None

        return Signal(
            strategy=self.name,
            symbol=candle.symbol,
            side=Side.BUY if fast_above else Side.SELL,
            price=candle.close,
            time=candle.close_time,
            reason=f"SMA{self.fast}={fast_sma:.8f} crossed SMA{self.slow}={slow_sma:.8f}",
        )

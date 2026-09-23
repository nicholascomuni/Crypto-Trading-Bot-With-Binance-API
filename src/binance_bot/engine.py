"""Event loop wiring candles to strategies and signals to handlers.

Execution is simulated only: :class:`PaperBroker` records hypothetical fills at the
signal price. No order is ever sent to Binance.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from binance_bot.models import Candle
from binance_bot.strategy import Side, Signal, Strategy

logger = logging.getLogger(__name__)

SignalHandler = Callable[[Signal], Awaitable[None] | None]
CandleHandler = Callable[[Candle], Awaitable[None] | None]


class Engine:
    """Fan each closed candle out to every strategy, then every signal out to every handler.

    A failing strategy or handler is logged and skipped so one bug cannot stop the loop.
    """

    def __init__(
        self,
        strategies: Iterable[Strategy],
        signal_handlers: Iterable[SignalHandler] = (),
        candle_handlers: Iterable[CandleHandler] = (),
    ) -> None:
        self.strategies = list(strategies)
        self.signal_handlers = list(signal_handlers)
        self.candle_handlers = list(candle_handlers)

    async def run(self, candles: AsyncIterable[Candle]) -> None:
        async for candle in candles:
            await self.process(candle)

    async def process(self, candle: Candle) -> list[Signal]:
        for handler in self.candle_handlers:
            await _call(handler, candle)

        signals: list[Signal] = []
        for strategy in self.strategies:
            try:
                signal = strategy.on_candle(candle)
            except Exception:
                logger.exception("Strategy %s failed on %s", strategy.name, candle)
                continue
            if signal is not None:
                signals.append(signal)

        for signal in signals:
            for handler in self.signal_handlers:
                await _call(handler, signal)
        return signals


async def _call(handler: Callable[[object], Awaitable[None] | None], arg: object) -> None:
    try:
        result = handler(arg)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.exception("Handler %r failed", handler)


def log_signal(signal: Signal) -> None:
    """Signal handler that just logs the signal."""
    logger.info(
        "SIGNAL %s %s @ %s [%s] %s",
        signal.side,
        signal.symbol,
        signal.price,
        signal.strategy,
        signal.reason,
    )


@dataclass(frozen=True, slots=True)
class PaperTrade:
    symbol: str
    entry_time: datetime
    entry_price: Decimal
    exit_time: datetime
    exit_price: Decimal
    quantity: Decimal
    pnl: Decimal


@dataclass
class _Position:
    quantity: Decimal
    entry_price: Decimal
    entry_time: datetime
    entry_fee: Decimal


class PaperBroker:
    """Long-only simulated execution: BUY opens a fixed-notional position, SELL closes it.

    Fills happen at the signal price with a proportional fee; there is no slippage,
    partial fill or latency model. It exists to exercise the signal path end to end,
    not to estimate real performance.
    """

    def __init__(self, notional: Decimal = Decimal("100"), fee_rate: Decimal = Decimal("0.001")) -> None:
        self.notional = notional
        self.fee_rate = fee_rate
        self.positions: dict[str, _Position] = {}
        self.trades: list[PaperTrade] = []

    def __call__(self, signal: Signal) -> None:
        position = self.positions.get(signal.symbol)
        if signal.side is Side.BUY and position is None:
            quantity = self.notional / signal.price
            self.positions[signal.symbol] = _Position(
                quantity=quantity,
                entry_price=signal.price,
                entry_time=signal.time,
                entry_fee=self.notional * self.fee_rate,
            )
            logger.info("PAPER open %s qty=%s @ %s", signal.symbol, quantity, signal.price)
        elif signal.side is Side.SELL and position is not None:
            proceeds = position.quantity * signal.price
            pnl = proceeds - self.notional - position.entry_fee - proceeds * self.fee_rate
            trade = PaperTrade(
                symbol=signal.symbol,
                entry_time=position.entry_time,
                entry_price=position.entry_price,
                exit_time=signal.time,
                exit_price=signal.price,
                quantity=position.quantity,
                pnl=pnl,
            )
            self.trades.append(trade)
            del self.positions[signal.symbol]
            logger.info(
                "PAPER close %s @ %s pnl=%s", signal.symbol, signal.price, pnl.quantize(Decimal("0.0001"))
            )

    @property
    def realized_pnl(self) -> Decimal:
        return sum((t.pnl for t in self.trades), Decimal(0))

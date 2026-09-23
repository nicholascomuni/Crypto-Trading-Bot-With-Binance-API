from datetime import UTC, datetime
from decimal import Decimal

from binance_bot.engine import Engine, PaperBroker
from binance_bot.models import Candle
from binance_bot.strategy import Side, Signal, SmaCrossStrategy
from factories import make_candles

NOW = datetime(2024, 1, 1, tzinfo=UTC)


def signal(side: Side, price: str, symbol: str = "BTCUSDT") -> Signal:
    return Signal(strategy="test", symbol=symbol, side=side, price=Decimal(price), time=NOW)


async def aiter_list(items):
    for item in items:
        yield item


class Boom:
    name = "boom"

    def on_candle(self, candle: Candle) -> Signal | None:
        raise RuntimeError("bug in strategy")


async def test_engine_routes_signals_to_sync_and_async_handlers() -> None:
    received: list[Signal] = []
    seen: list[Candle] = []

    async def async_handler(s: Signal) -> None:
        received.append(s)

    def failing_handler(s: Signal) -> None:
        raise RuntimeError("handler bug")

    engine = Engine(
        [Boom(), SmaCrossStrategy(fast=2, slow=4)],
        signal_handlers=[failing_handler, async_handler],
        candle_handlers=[seen.append],
    )
    candles = make_candles([10, 9, 8, 7, 6, 10, 12, 12, 8])
    await engine.run(aiter_list(candles))

    assert len(seen) == len(candles)
    assert [s.side for s in received] == [Side.BUY, Side.SELL]


def test_paper_broker_round_trip_with_fees() -> None:
    broker = PaperBroker(notional=Decimal("100"), fee_rate=Decimal("0.001"))
    broker(signal(Side.BUY, "50"))
    broker(signal(Side.BUY, "40"))  # already long: ignored
    assert broker.positions["BTCUSDT"].quantity == Decimal("2")

    broker(signal(Side.SELL, "55"))
    assert broker.positions == {}
    [trade] = broker.trades
    # proceeds 110 - notional 100 - entry fee 0.1 - exit fee 0.11
    assert trade.pnl == Decimal("9.79")
    assert broker.realized_pnl == Decimal("9.79")


def test_paper_broker_ignores_sell_when_flat() -> None:
    broker = PaperBroker()
    broker(signal(Side.SELL, "10"))
    assert broker.trades == []
    assert broker.positions == {}

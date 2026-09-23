from decimal import Decimal

import pytest

from binance_bot.strategy import Side, SmaCrossStrategy, Strategy
from factories import make_candles


def run(strategy: SmaCrossStrategy, closes: list[float], symbol: str = "BTCUSDT"):
    return [(i, s) for i, c in enumerate(make_candles(closes, symbol)) if (s := strategy.on_candle(c))]


def test_is_a_strategy() -> None:
    assert isinstance(SmaCrossStrategy(), Strategy)


def test_invalid_windows() -> None:
    with pytest.raises(ValueError, match="fast < slow"):
        SmaCrossStrategy(fast=5, slow=5)


def test_no_signal_during_warmup_or_steady_trend() -> None:
    strategy = SmaCrossStrategy(fast=2, slow=4)
    assert run(strategy, [10, 11, 12, 13, 14, 15, 16]) == []


def test_buy_on_upward_cross_and_sell_on_downward_cross() -> None:
    strategy = SmaCrossStrategy(fast=2, slow=4)
    closes = [10, 9, 8, 7, 6, 10, 12, 12, 8, 5, 4]
    signals = run(strategy, closes)

    assert [(i, s.side) for i, s in signals] == [(5, Side.BUY), (8, Side.SELL)]
    _, buy = signals[0]
    assert buy.price == Decimal("10")
    assert buy.symbol == "BTCUSDT"
    assert buy.strategy == "sma_cross_2_4"
    assert "crossed" in buy.reason


def test_state_is_kept_per_symbol() -> None:
    strategy = SmaCrossStrategy(fast=2, slow=4)
    btc = make_candles([10, 9, 8, 7, 6, 10], "BTCUSDT")
    eth = make_candles([1, 1.1, 1.2, 1.3, 1.4, 1.5], "ETHUSDT")
    signals = []
    for b, e in zip(btc, eth, strict=True):
        signals += [s for s in (strategy.on_candle(b), strategy.on_candle(e)) if s]
    assert [(s.symbol, s.side) for s in signals] == [("BTCUSDT", Side.BUY)]


def test_warm_up_discards_signals_but_keeps_state() -> None:
    strategy = SmaCrossStrategy(fast=2, slow=4)
    candles = make_candles([10, 9, 8, 7, 6, 10, 12])
    strategy.warm_up(candles[:5])
    assert strategy.on_candle(candles[5]).side is Side.BUY

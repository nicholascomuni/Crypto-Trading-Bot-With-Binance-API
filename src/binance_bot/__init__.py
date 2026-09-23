"""Reusable foundation for a Binance trading bot: market data, strategies and paper execution."""

from binance_bot.engine import Engine, PaperBroker, PaperTrade, log_signal
from binance_bot.models import Candle
from binance_bot.rest import BinanceAPIError, BinanceRestClient
from binance_bot.strategy import Side, Signal, SmaCrossStrategy, Strategy
from binance_bot.stream import Backoff, KlineStream, StreamGaveUpError

__all__ = [
    "Backoff",
    "BinanceAPIError",
    "BinanceRestClient",
    "Candle",
    "Engine",
    "KlineStream",
    "PaperBroker",
    "PaperTrade",
    "Side",
    "Signal",
    "SmaCrossStrategy",
    "Strategy",
    "StreamGaveUpError",
    "log_signal",
]

__version__ = "0.2.0"

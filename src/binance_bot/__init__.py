"""Reusable foundation for a Binance trading bot: market data, strategies and paper execution."""

from binance_bot.models import Candle
from binance_bot.rest import BinanceAPIError, BinanceRestClient
from binance_bot.stream import Backoff, KlineStream, StreamGaveUpError

__all__ = [
    "Backoff",
    "BinanceAPIError",
    "BinanceRestClient",
    "Candle",
    "KlineStream",
    "StreamGaveUpError",
]

__version__ = "0.2.0"

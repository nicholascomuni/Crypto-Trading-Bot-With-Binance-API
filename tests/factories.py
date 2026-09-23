"""Builders for synthetic Binance payloads used across the tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from binance_bot.models import Candle, datetime_to_ms

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def rest_row(open_ms: int, close: str = "100.0", minutes: int = 1) -> list[Any]:
    """A kline row shaped like ``GET /api/v3/klines`` output."""
    return [
        open_ms,
        "99.0",
        "101.0",
        "98.5",
        close,
        "12.5",
        open_ms + minutes * 60_000 - 1,
        "1250.0",
        42,
        "6.0",
        "600.0",
        "0",
    ]


def ws_event(symbol: str, open_ms: int, close: str = "100.0", closed: bool = True) -> dict[str, Any]:
    """A ``<symbol>@kline_1m`` event payload (the ``data`` part of a combined-stream message)."""
    return {
        "e": "kline",
        "E": open_ms + 60_000,
        "s": symbol,
        "k": {
            "t": open_ms,
            "T": open_ms + 59_999,
            "s": symbol,
            "i": "1m",
            "o": "99.0",
            "c": close,
            "h": "101.0",
            "l": "98.5",
            "v": "12.5",
            "n": 42,
            "x": closed,
            "q": "1250.0",
        },
    }


def make_candles(closes: list[float | str], symbol: str = "BTCUSDT") -> list[Candle]:
    start = datetime_to_ms(T0)
    return [
        Candle.from_rest(symbol, "1m", rest_row(start + i * 60_000, close=str(c)))
        for i, c in enumerate(closes)
    ]

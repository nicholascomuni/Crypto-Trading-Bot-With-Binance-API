"""Core market-data types and the single place where Binance kline payloads are parsed."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

# Kline intervals supported by Binance spot.
INTERVALS: tuple[str, ...] = (
    "1s", "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
)  # fmt: skip

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def validate_interval(interval: str) -> str:
    """Return ``interval`` unchanged if Binance supports it, otherwise raise ``ValueError``."""
    if interval not in INTERVALS:
        supported = ", ".join(INTERVALS)
        raise ValueError(f"Unsupported interval {interval!r}; expected one of: {supported}")
    return interval


def ms_to_datetime(ms: int) -> datetime:
    """Convert a Binance millisecond timestamp to a timezone-aware UTC datetime."""
    return _EPOCH + timedelta(milliseconds=int(ms))


def datetime_to_ms(dt: datetime) -> int:
    """Convert a datetime to Binance milliseconds. Naive datetimes are interpreted as UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (dt - _EPOCH) // timedelta(milliseconds=1)


@dataclass(frozen=True, slots=True)
class Candle:
    """One OHLCV kline. Prices and volumes are ``Decimal`` to avoid float rounding."""

    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal
    trades: int
    closed: bool = True

    @classmethod
    def from_rest(cls, symbol: str, interval: str, row: Sequence[Any], *, closed: bool = True) -> Candle:
        """Parse one row of ``GET /api/v3/klines``.

        Row layout: ``[open_time, open, high, low, close, volume, close_time,
        quote_volume, trades, taker_base_volume, taker_quote_volume, ignore]``.
        The REST API does not flag the still-forming kline, so callers pass ``closed``.
        """
        return cls._build(
            symbol=symbol,
            interval=interval,
            open_time=row[0],
            close_time=row[6],
            open_=row[1],
            high=row[2],
            low=row[3],
            close=row[4],
            volume=row[5],
            quote_volume=row[7],
            trades=row[8],
            closed=closed,
        )

    @classmethod
    def from_ws_event(cls, event: Mapping[str, Any]) -> Candle:
        """Parse a ``<symbol>@kline_<interval>`` websocket event (the object holding ``"k"``)."""
        k = event["k"]
        return cls._build(
            symbol=k["s"],
            interval=k["i"],
            open_time=k["t"],
            close_time=k["T"],
            open_=k["o"],
            high=k["h"],
            low=k["l"],
            close=k["c"],
            volume=k["v"],
            quote_volume=k["q"],
            trades=k["n"],
            closed=k["x"],
        )

    @classmethod
    def _build(
        cls,
        *,
        symbol: str,
        interval: str,
        open_time: int,
        close_time: int,
        open_: str,
        high: str,
        low: str,
        close: str,
        volume: str,
        quote_volume: str,
        trades: int,
        closed: bool,
    ) -> Candle:
        return cls(
            symbol=symbol.upper(),
            interval=interval,
            open_time=ms_to_datetime(open_time),
            close_time=ms_to_datetime(close_time),
            open=Decimal(open_),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal(volume),
            quote_volume=Decimal(quote_volume),
            trades=int(trades),
            closed=bool(closed),
        )

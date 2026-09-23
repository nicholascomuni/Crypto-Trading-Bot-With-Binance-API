from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from binance_bot.models import Candle, datetime_to_ms, ms_to_datetime, validate_interval
from factories import rest_row, ws_event

OPEN_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z


def test_from_rest_parses_decimals_and_utc_times() -> None:
    candle = Candle.from_rest("btcusdt", "1m", rest_row(OPEN_MS, close="42000.12345678"))

    assert candle.symbol == "BTCUSDT"
    assert candle.close == Decimal("42000.12345678")
    assert isinstance(candle.open, Decimal)
    assert candle.open_time == datetime(2024, 1, 1, tzinfo=UTC)
    assert candle.close_time == datetime(2024, 1, 1, 0, 0, 59, 999_000, tzinfo=UTC)
    assert candle.trades == 42
    assert candle.closed is True


def test_ws_and_rest_payloads_produce_identical_candles() -> None:
    from_ws = Candle.from_ws_event(ws_event("BTCUSDT", OPEN_MS, close="101.5"))
    from_rest = Candle.from_rest("BTCUSDT", "1m", rest_row(OPEN_MS, close="101.5"))

    assert from_ws == from_rest


def test_ws_open_kline_is_flagged() -> None:
    assert Candle.from_ws_event(ws_event("ETHUSDT", OPEN_MS, closed=False)).closed is False


def test_candle_is_immutable() -> None:
    candle = Candle.from_rest("BTCUSDT", "1m", rest_row(OPEN_MS))
    with pytest.raises(AttributeError):
        candle.close = Decimal(1)  # type: ignore[misc]


def test_ms_round_trip_and_naive_datetimes_are_utc() -> None:
    assert datetime_to_ms(ms_to_datetime(OPEN_MS + 123)) == OPEN_MS + 123
    assert datetime_to_ms(datetime(2024, 1, 1)) == OPEN_MS
    plus_two = timezone(timedelta(hours=2))
    assert datetime_to_ms(datetime(2024, 1, 1, 2, tzinfo=plus_two)) == OPEN_MS


def test_validate_interval() -> None:
    assert validate_interval("15m") == "15m"
    with pytest.raises(ValueError, match="Unsupported interval"):
        validate_interval("7m")

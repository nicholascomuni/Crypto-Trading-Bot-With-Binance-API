import csv
from datetime import UTC, datetime

import httpx
import respx

from binance_bot.cli import build_parser, main, parse_utc
from binance_bot.models import datetime_to_ms
from binance_bot.rest import KLINES_PATH
from factories import rest_row

BASE = "https://api.test"


def test_parse_utc() -> None:
    assert parse_utc("2024-01-01") == datetime(2024, 1, 1, tzinfo=UTC)
    assert parse_utc("2024-01-01T03:00:00+02:00") == datetime(2024, 1, 1, 1, tzinfo=UTC)


def test_stream_arguments() -> None:
    args = build_parser().parse_args(["stream", "--symbols", "BTCUSDT,ETHUSDT", "--interval", "5m"])
    assert args.symbols == "BTCUSDT,ETHUSDT"
    assert args.interval == "5m"
    assert (args.fast, args.slow) == (9, 21)


@respx.mock
def test_history_writes_csv(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BINANCE_REST_URL", BASE)
    start_ms = datetime_to_ms(datetime(2024, 1, 1, tzinfo=UTC))
    respx.get(BASE + KLINES_PATH).mock(
        return_value=httpx.Response(
            200, json=[rest_row(start_ms + i * 3_600_000, minutes=60) for i in range(3)]
        )
    )
    out = tmp_path / "data" / "btc.csv"

    code = main(["history", "--symbol", "BTCUSDT", "--interval", "1h", "--start", "2024-01-01",
                 "--end", "2024-01-01T02:00", "--out", str(out)])  # fmt: skip

    assert code == 0
    with out.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3
    assert rows[0]["open_time"] == "2024-01-01T00:00:00+00:00"
    assert rows[2]["close_time"] == "2024-01-01T02:59:59.999000+00:00"
    assert rows[0]["close"] == "100.0"

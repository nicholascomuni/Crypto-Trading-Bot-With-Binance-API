from datetime import UTC, datetime

import httpx
import pytest
import respx

from binance_bot.models import datetime_to_ms
from binance_bot.rest import KLINES_PATH, BinanceAPIError, BinanceRestClient
from factories import rest_row

BASE = "https://api.test"
URL = BASE + KLINES_PATH
START = datetime(2024, 1, 1, tzinfo=UTC)
START_MS = datetime_to_ms(START)
MINUTE = 60_000


class RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def rows(first_ms: int, count: int) -> list[list[object]]:
    return [rest_row(first_ms + i * MINUTE) for i in range(count)]


@respx.mock
async def test_get_klines_paginates_until_short_page() -> None:
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json=rows(START_MS, 3)),
            httpx.Response(200, json=rows(START_MS + 3 * MINUTE, 3)),
            httpx.Response(200, json=rows(START_MS + 6 * MINUTE, 1)),
        ]
    )
    end = datetime(2024, 1, 2, tzinfo=UTC)

    async with BinanceRestClient(BASE) as client:
        pages = [page async for page in client.iter_klines("btcusdt", "1m", START, end, page_size=3)]

    assert [len(p) for p in pages] == [3, 3, 1]
    candles = [c for page in pages for c in page]
    assert [datetime_to_ms(c.open_time) for c in candles] == [START_MS + i * MINUTE for i in range(7)]

    sent = [call.request.url.params for call in route.calls]
    assert [int(p["startTime"]) for p in sent] == [
        START_MS,
        START_MS + 2 * MINUTE + 1,
        START_MS + 5 * MINUTE + 1,
    ]
    assert all(p["symbol"] == "BTCUSDT" and p["endTime"] == str(datetime_to_ms(end)) for p in sent)


@respx.mock
async def test_get_klines_stops_on_empty_page() -> None:
    respx.get(URL).mock(
        side_effect=[httpx.Response(200, json=rows(START_MS, 2)), httpx.Response(200, json=[])]
    )
    async with BinanceRestClient(BASE) as client:
        candles = [c async for page in client.iter_klines("BTCUSDT", "1m", START, page_size=2) for c in page]
    assert len(candles) == 2


@respx.mock
async def test_get_klines_default_page_size_covers_more_than_500_candles() -> None:
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json=rows(START_MS, 1000)),
            httpx.Response(200, json=rows(START_MS + 1000 * MINUTE, 440)),
        ]
    )
    async with BinanceRestClient(BASE) as client:
        candles = await client.get_klines("BTCUSDT", "1m", START, datetime(2024, 1, 2, tzinfo=UTC))
    assert len(candles) == 1440
    assert all(c.closed for c in candles)


@respx.mock
async def test_retries_on_429_honouring_retry_after() -> None:
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}, json={"code": -1003, "msg": "Too many"}),
            httpx.Response(503),
            httpx.Response(200, json=rows(START_MS, 1)),
        ]
    )
    sleep = RecordingSleep()
    async with BinanceRestClient(BASE, sleep=sleep, backoff_base=0.5) as client:
        candles = await client.get_latest_klines("BTCUSDT", "1m", limit=1)

    assert len(candles) == 1
    assert sleep.calls == [7.0, 1.0]  # Retry-After, then 0.5 * 2**1


@respx.mock
async def test_retries_on_transport_error() -> None:
    respx.get(URL).mock(side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json=rows(START_MS, 1))])
    sleep = RecordingSleep()
    async with BinanceRestClient(BASE, sleep=sleep) as client:
        assert len(await client.get_latest_klines("BTCUSDT", "1m", limit=1)) == 1
    assert len(sleep.calls) == 1


@respx.mock
async def test_client_errors_are_not_retried() -> None:
    route = respx.get(URL).mock(
        return_value=httpx.Response(400, json={"code": -1121, "msg": "Invalid symbol."})
    )
    async with BinanceRestClient(BASE, sleep=RecordingSleep()) as client:
        with pytest.raises(BinanceAPIError) as excinfo:
            await client.get_latest_klines("NOPE", "1m")
    assert excinfo.value.code == -1121
    assert route.call_count == 1


@respx.mock
async def test_ip_ban_418_is_not_retried() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(418, headers={"Retry-After": "120"}))
    async with BinanceRestClient(BASE, sleep=RecordingSleep()) as client:
        with pytest.raises(BinanceAPIError):
            await client.get_latest_klines("BTCUSDT", "1m")
    assert route.call_count == 1


@respx.mock
async def test_gives_up_after_max_retries() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(502))
    sleep = RecordingSleep()
    async with BinanceRestClient(BASE, sleep=sleep, max_retries=2) as client:
        with pytest.raises(BinanceAPIError):
            await client.get_latest_klines("BTCUSDT", "1m")
    assert route.call_count == 3
    assert len(sleep.calls) == 2


@respx.mock
async def test_pauses_when_request_weight_is_near_limit() -> None:
    respx.get(URL).mock(
        return_value=httpx.Response(200, headers={"X-MBX-USED-WEIGHT-1M": "5900"}, json=rows(START_MS, 1))
    )
    sleep = RecordingSleep()
    async with BinanceRestClient(BASE, sleep=sleep, weight_limit=6000) as client:
        await client.get_latest_klines("BTCUSDT", "1m", limit=1)
        assert client.used_weight == 5900
    assert len(sleep.calls) == 1
    assert 0 < sleep.calls[0] <= 60


async def test_rejects_unknown_interval() -> None:
    async with BinanceRestClient(BASE) as client:
        with pytest.raises(ValueError, match="Unsupported interval"):
            await client.get_klines("BTCUSDT", "2m", START)

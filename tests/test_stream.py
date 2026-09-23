import json
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosedError, InvalidStatus
from websockets.http11 import Response

from binance_bot.stream import Backoff, KlineStream, StreamGaveUpError
from factories import ws_event

OPEN_MS = 1_704_067_200_000


def message(symbol: str, minute: int, closed: bool = True) -> str:
    stream = f"{symbol.lower()}@kline_1m"
    return json.dumps({"stream": stream, "data": ws_event(symbol, OPEN_MS + minute * 60_000, closed=closed)})


class FakeServer:
    """Scripted connections: each item is a list of messages followed by a disconnect,
    or an exception raised while connecting."""

    def __init__(self, script: list[list[str] | Exception]) -> None:
        self.script = list(script)
        self.urls: list[str] = []

    def connect(self, url: str):  # matches the ``Connect`` factory signature
        self.urls.append(url)
        step = self.script.pop(0)

        @asynccontextmanager
        async def _cm() -> AsyncIterator[AsyncIterator[str]]:
            if isinstance(step, Exception):
                raise step
            yield self._messages(step)

        return _cm()

    @staticmethod
    async def _messages(messages: list[str]) -> AsyncIterator[str]:
        for m in messages:
            yield m
        raise ConnectionClosedError(None, None)


class RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def invalid_status(status: int) -> InvalidStatus:
    return InvalidStatus(Response(status, "", Headers()))


async def take(stream: KlineStream, n: int) -> list:
    out = []
    async for candle in stream:
        out.append(candle)
        if len(out) == n:
            break
    return out


def test_combined_stream_url() -> None:
    stream = KlineStream(["btcusdt", " ETHUSDT "], "1m", base_url="wss://example/")
    assert stream.url == "wss://example/stream?streams=btcusdt@kline_1m/ethusdt@kline_1m"


def test_requires_symbols() -> None:
    with pytest.raises(ValueError, match="symbol"):
        KlineStream([" "], "1m")


async def test_yields_only_closed_candles_and_skips_garbage() -> None:
    server = FakeServer(
        [
            [
                message("BTCUSDT", 0, closed=False),
                "not json",
                json.dumps({"result": None, "id": 1}),
                message("BTCUSDT", 0),
                message("ETHUSDT", 0),
            ]
        ]
    )
    stream = KlineStream(["BTCUSDT", "ETHUSDT"], "1m", connect=server.connect, sleep=RecordingSleep())
    candles = await take(stream, 2)
    assert [(c.symbol, c.closed) for c in candles] == [("BTCUSDT", True), ("ETHUSDT", True)]


async def test_reconnects_with_backoff_after_disconnects_and_errors() -> None:
    server = FakeServer(
        [
            [message("BTCUSDT", 0)],
            OSError("network down"),
            invalid_status(503),
            [message("BTCUSDT", 1)],
        ]
    )
    sleep = RecordingSleep()
    backoff = Backoff(base=1, factor=2, max_delay=60, rng=random.Random(0))
    stream = KlineStream(["BTCUSDT"], "1m", connect=server.connect, sleep=sleep, backoff=backoff)

    candles = await take(stream, 2)

    assert [c.open_time.minute for c in candles] == [0, 1]
    assert len(server.urls) == 4
    assert stream.reconnects == 3
    # Attempts 0, 1, 2 -> ceilings 1, 2, 4 with equal jitter in [ceiling/2, ceiling].
    for delay, ceiling in zip(sleep.calls, [1, 2, 4], strict=True):
        assert ceiling / 2 <= delay <= ceiling
    # Receiving data on the last connection resets the backoff.
    assert backoff.attempt == 0


async def test_fatal_handshake_status_is_raised() -> None:
    server = FakeServer([invalid_status(451)])
    stream = KlineStream(["BTCUSDT"], "1m", connect=server.connect, sleep=RecordingSleep())
    with pytest.raises(InvalidStatus):
        await take(stream, 1)


async def test_gives_up_after_max_consecutive_failures() -> None:
    server = FakeServer([OSError("x")] * 3)
    sleep = RecordingSleep()
    stream = KlineStream(["BTCUSDT"], "1m", connect=server.connect, sleep=sleep, max_consecutive_failures=2)
    with pytest.raises(StreamGaveUpError):
        await take(stream, 1)
    assert len(sleep.calls) == 2


def test_backoff_grows_is_capped_and_resets() -> None:
    backoff = Backoff(base=1, factor=2, max_delay=10, rng=random.Random(1))
    delays = [backoff.next_delay() for _ in range(8)]
    ceilings = [1, 2, 4, 8, 10, 10, 10, 10]
    assert all(c / 2 <= d <= c for d, c in zip(delays, ceilings, strict=True))
    backoff.reset()
    assert backoff.next_delay() <= 1

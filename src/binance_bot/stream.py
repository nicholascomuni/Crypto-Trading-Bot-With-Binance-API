"""Resilient websocket stream of closed klines for one or more symbols."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field

from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidStatus

from binance_bot.models import Candle, validate_interval

logger = logging.getLogger(__name__)

DEFAULT_WS_URL = "wss://stream.binance.com:9443"

Sleep = Callable[[float], Awaitable[None]]


Connect = Callable[[str], AbstractAsyncContextManager[AsyncIterable[str | bytes]]]
"""Factory returning an async context manager that yields an iterable websocket connection."""


@dataclass
class Backoff:
    """Exponential backoff with "equal jitter": half the delay is fixed, half is random.

    ``next_delay()`` grows as ``base * factor**attempt`` up to ``max_delay``; ``reset()``
    is called once a connection proves healthy.
    """

    base: float = 1.0
    factor: float = 2.0
    max_delay: float = 60.0
    rng: random.Random = field(default_factory=random.Random)
    attempt: int = 0

    def next_delay(self) -> float:
        ceiling = min(self.max_delay, self.base * self.factor**self.attempt)
        self.attempt += 1
        return ceiling / 2 + self.rng.uniform(0, ceiling / 2)

    def reset(self) -> None:
        self.attempt = 0


class StreamGaveUpError(RuntimeError):
    """Raised when ``max_consecutive_failures`` reconnect attempts have failed."""


class KlineStream:
    """Subscribe to ``<symbol>@kline_<interval>`` for many symbols over one combined stream.

    Iterating the stream yields :class:`Candle` objects, by default only once a kline has
    closed. Dropped connections (including Binance's forced disconnect after 24h) are
    re-established automatically with exponential backoff and jitter. Handshake rejections
    with a 4xx status other than 429 (e.g. HTTP 451 for restricted locations) are raised
    immediately because retrying cannot fix them.
    """

    def __init__(
        self,
        symbols: Iterable[str],
        interval: str,
        *,
        base_url: str = DEFAULT_WS_URL,
        only_closed: bool = True,
        backoff: Backoff | None = None,
        max_consecutive_failures: int | None = None,
        connect: Connect = ws_connect,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        if not self.symbols:
            raise ValueError("At least one symbol is required")
        self.interval = validate_interval(interval)
        self.only_closed = only_closed
        self.backoff = backoff or Backoff()
        self.max_consecutive_failures = max_consecutive_failures
        self.reconnects = 0
        self._base_url = base_url.rstrip("/")
        self._connect = connect
        self._sleep = sleep

    @property
    def url(self) -> str:
        streams = "/".join(f"{s.lower()}@kline_{self.interval}" for s in self.symbols)
        return f"{self._base_url}/stream?streams={streams}"

    async def __aiter__(self) -> AsyncIterator[Candle]:
        failures = 0
        while True:
            try:
                async with self._connect(self.url) as ws:
                    logger.info("Connected to %s", self.url)
                    async for raw in ws:
                        candle = self._parse(raw)
                        if candle is None:
                            continue
                        # A parsed message proves the connection is healthy.
                        failures = 0
                        self.backoff.reset()
                        if candle.closed or not self.only_closed:
                            yield candle
                logger.warning("Stream closed by server")
            except InvalidStatus as exc:
                status = exc.response.status_code
                if 400 <= status < 500 and status != 429:
                    raise
                logger.warning("Handshake rejected with HTTP %s", status)
            except (ConnectionClosed, InvalidHandshake, OSError, TimeoutError) as exc:
                logger.warning("Stream connection lost: %r", exc)

            failures += 1
            if self.max_consecutive_failures is not None and failures > self.max_consecutive_failures:
                raise StreamGaveUpError(f"Gave up after {failures - 1} consecutive reconnect attempts")
            delay = self.backoff.next_delay()
            self.reconnects += 1
            logger.info("Reconnecting in %.1fs", delay)
            await self._sleep(delay)

    @staticmethod
    def _parse(raw: str | bytes) -> Candle | None:
        try:
            message = json.loads(raw)
            return Candle.from_ws_event(message["data"])
        except (ValueError, KeyError, TypeError) as exc:
            logger.debug("Ignoring unexpected message %r (%s)", raw, exc)
            return None

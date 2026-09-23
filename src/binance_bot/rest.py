"""Async client for Binance public REST market-data endpoints."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from types import TracebackType
from typing import Any, Self

import httpx

from binance_bot.models import Candle, datetime_to_ms, validate_interval

logger = logging.getLogger(__name__)

DEFAULT_REST_URL = "https://api.binance.com"
KLINES_PATH = "/api/v3/klines"
MAX_KLINES_PER_REQUEST = 1000
# Binance's default request-weight budget for spot is 6000 per minute per IP.
DEFAULT_WEIGHT_LIMIT = 6000
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

Sleep = Callable[[float], Awaitable[None]]


class BinanceAPIError(Exception):
    """Non-retryable error returned by the Binance REST API."""

    def __init__(self, status: int, code: int | None, message: str) -> None:
        super().__init__(f"HTTP {status} (code={code}): {message}")
        self.status = status
        self.code = code
        self.message = message


class BinanceRestClient:
    """Minimal async REST client with retries and request-weight awareness.

    Only public, unsigned endpoints are implemented; no API key is needed.

    Retries use exponential backoff for transport errors, HTTP 429 and 5xx, honouring
    ``Retry-After`` when Binance sends it. HTTP 418 (IP ban) is never retried. After each
    response the ``X-MBX-USED-WEIGHT-1M`` header is checked and, once usage crosses
    ``weight_threshold`` of the limit, the client pauses until the next minute window.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_REST_URL,
        *,
        timeout: float = 10.0,
        max_retries: int = 5,
        backoff_base: float = 0.5,
        weight_limit: int = DEFAULT_WEIGHT_LIMIT,
        weight_threshold: float = 0.9,
        http_client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._client = http_client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._owns_client = http_client is None
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._weight_limit = weight_limit
        self._weight_threshold = weight_threshold
        self._sleep = sleep
        self.used_weight: int | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime | None = None,
    ) -> list[Candle]:
        """Return every kline opened in ``[start, end]``, paging through the API as needed."""
        return [candle async for page in self.iter_klines(symbol, interval, start, end) for candle in page]

    async def get_latest_klines(
        self, symbol: str, interval: str, limit: int = MAX_KLINES_PER_REQUEST
    ) -> list[Candle]:
        """Return the most recent ``limit`` klines; the last one may still be open."""
        validate_interval(interval)
        symbol = symbol.upper()
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return _to_candles(symbol, interval, await self._get(KLINES_PATH, params))

    async def iter_klines(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime | None = None,
        *,
        page_size: int = MAX_KLINES_PER_REQUEST,
    ) -> AsyncIterator[list[Candle]]:
        """Yield pages of klines opened in ``[start, end]`` (``end`` defaults to now).

        Naive datetimes are interpreted as UTC.
        """
        validate_interval(interval)
        if not 1 <= page_size <= MAX_KLINES_PER_REQUEST:
            raise ValueError(f"page_size must be in [1, {MAX_KLINES_PER_REQUEST}]")
        symbol = symbol.upper()
        cursor = datetime_to_ms(start)
        end_ms = datetime_to_ms(end) if end is not None else int(time.time() * 1000)

        while cursor <= end_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": page_size,
            }
            rows = await self._get(KLINES_PATH, params)
            if not rows:
                return
            yield _to_candles(symbol, interval, rows)
            if len(rows) < page_size:
                return
            cursor = int(rows[-1][0]) + 1

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        attempt = 0
        while True:
            try:
                response = await self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise
                delay = self._backoff_base * 2**attempt
                logger.warning("GET %s failed (%s); retrying in %.1fs", path, exc, delay)
            else:
                await self._track_weight(response)
                if response.is_success:
                    return response.json()
                if response.status_code not in RETRYABLE_STATUS or attempt >= self._max_retries:
                    raise _api_error(response)
                delay = _retry_after(response) or self._backoff_base * 2**attempt
                logger.warning(
                    "GET %s returned HTTP %s; retrying in %.1fs", path, response.status_code, delay
                )
            attempt += 1
            await self._sleep(delay)

    async def _track_weight(self, response: httpx.Response) -> None:
        header = response.headers.get("x-mbx-used-weight-1m")
        if header is None:
            return
        self.used_weight = int(header)
        if self.used_weight >= self._weight_limit * self._weight_threshold:
            pause = 60 - time.time() % 60
            logger.warning(
                "Request weight %s/%s used; pausing %.1fs until the next window",
                self.used_weight,
                self._weight_limit,
                pause,
            )
            await self._sleep(pause)


def _to_candles(symbol: str, interval: str, rows: list[list[Any]]) -> list[Candle]:
    # The REST API does not flag the still-forming kline; infer it from its close time.
    now_ms = int(time.time() * 1000)
    return [Candle.from_rest(symbol, interval, row, closed=int(row[6]) < now_ms) for row in rows]


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _api_error(response: httpx.Response) -> BinanceAPIError:
    try:
        body = response.json()
        return BinanceAPIError(response.status_code, body.get("code"), body.get("msg", ""))
    except (ValueError, AttributeError):
        return BinanceAPIError(response.status_code, None, response.text[:200])

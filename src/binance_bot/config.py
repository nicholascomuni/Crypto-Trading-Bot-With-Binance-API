"""Runtime settings read from environment variables.

Only public market-data endpoints are used, so no API key or secret is required.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from binance_bot.rest import DEFAULT_REST_URL
from binance_bot.stream import DEFAULT_WS_URL


@dataclass(frozen=True, slots=True)
class Settings:
    rest_url: str = DEFAULT_REST_URL
    ws_url: str = DEFAULT_WS_URL
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        return cls(
            rest_url=env.get("BINANCE_REST_URL", DEFAULT_REST_URL),
            ws_url=env.get("BINANCE_WS_URL", DEFAULT_WS_URL),
            log_level=env.get("LOG_LEVEL", "INFO").upper(),
        )

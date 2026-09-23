"""Command-line entry point: ``python -m binance_bot {stream,history} ...``."""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from binance_bot.config import Settings
from binance_bot.engine import Engine, PaperBroker, log_signal
from binance_bot.models import INTERVALS, Candle
from binance_bot.rest import BinanceRestClient
from binance_bot.strategy import SmaCrossStrategy
from binance_bot.stream import KlineStream

logger = logging.getLogger("binance_bot")

CSV_FIELDS = (
    "symbol",
    "interval",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trades",
)


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 date/datetime; values without an offset are taken as UTC."""
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="binance_bot",
        description="Binance market data and signal-only strategy runner (no order execution).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    stream = sub.add_parser("stream", help="Stream closed candles and run the SMA strategy in paper mode")
    stream.add_argument("--symbols", required=True, help="Comma-separated, e.g. BTCUSDT,ETHUSDT")
    stream.add_argument("--interval", default="1m", choices=INTERVALS)
    stream.add_argument("--fast", type=int, default=9, help="Fast SMA length")
    stream.add_argument("--slow", type=int, default=21, help="Slow SMA length")
    stream.add_argument(
        "--notional", type=Decimal, default=Decimal("100"), help="Paper trade size in quote asset"
    )
    stream.add_argument(
        "--no-warmup", action="store_true", help="Skip seeding the strategy with REST history"
    )

    history = sub.add_parser("history", help="Download historical candles to CSV")
    history.add_argument("--symbol", required=True)
    history.add_argument("--interval", default="1h", choices=INTERVALS)
    history.add_argument(
        "--start", required=True, type=parse_utc, help="ISO date/time, UTC unless offset given"
    )
    history.add_argument("--end", type=parse_utc, help="ISO date/time (default: now)")
    history.add_argument("--out", type=Path, help="Output CSV path (default: stdout)")
    return parser


def write_csv(candles: Sequence[Candle], out: TextIO) -> None:
    writer = csv.writer(out)
    writer.writerow(CSV_FIELDS)
    for c in candles:
        writer.writerow(
            [
                c.symbol,
                c.interval,
                c.open_time.isoformat(),
                c.close_time.isoformat(),
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
                c.quote_volume,
                c.trades,
            ]
        )


async def run_history(args: argparse.Namespace, settings: Settings) -> int:
    async with BinanceRestClient(settings.rest_url) as client:
        candles = await client.get_klines(args.symbol, args.interval, args.start, args.end)
    if args.out is None:
        write_csv(candles, sys.stdout)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="") as fh:
            write_csv(candles, fh)
        logger.info("Wrote %d candles to %s", len(candles), args.out)
    return 0


async def run_stream(args: argparse.Namespace, settings: Settings, broker: PaperBroker) -> int:
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    strategy = SmaCrossStrategy(fast=args.fast, slow=args.slow)

    if not args.no_warmup:
        async with BinanceRestClient(settings.rest_url) as client:
            for symbol in symbols:
                history = await client.get_latest_klines(symbol, args.interval, limit=args.slow + 1)
                strategy.warm_up(c for c in history if c.closed)
        logger.info("Warmed up %s on %s", strategy.name, ", ".join(symbols))

    def log_candle(candle: Candle) -> None:
        logger.info(
            "%s %s close=%s O=%s H=%s L=%s V=%s",
            candle.symbol,
            candle.close_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            candle.close,
            candle.open,
            candle.high,
            candle.low,
            candle.volume,
        )

    engine = Engine([strategy], signal_handlers=[log_signal, broker], candle_handlers=[log_candle])
    await engine.run(KlineStream(symbols, args.interval, base_url=settings.ws_url))
    return 0


def print_paper_summary(broker: PaperBroker) -> None:
    print(f"\nPaper trades closed: {len(broker.trades)}")
    for t in broker.trades:
        print(f"  {t.symbol} {t.entry_price} -> {t.exit_price} pnl={t.pnl:.4f}")
    if broker.positions:
        print(f"Open paper positions: {', '.join(broker.positions)}")
    print(f"Realized paper PnL (quote asset): {broker.realized_pnl:.4f}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.command == "history":
        return asyncio.run(run_history(args, settings))

    broker = PaperBroker(notional=args.notional)
    try:
        return asyncio.run(run_stream(args, settings, broker))
    except KeyboardInterrupt:
        return 0
    finally:
        print_paper_summary(broker)

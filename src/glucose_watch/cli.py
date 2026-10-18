"""Command-line entry point: `python -m glucose_watch`.

This is the composition root, the one place that wires real settings,
the real clock, and the real Nightscout client together.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from glucose_watch import __version__
from glucose_watch.application.monitor import current_status, render_lines
from glucose_watch.domain.status import Thresholds
from glucose_watch.infrastructure.nightscout import NightscoutClient

DISCLAIMER = (
    "glucose_watch is a secondary, read-only display. It is not a medical device. "
    "Always confirm on the primary CGM app before acting."
)


class DemoSource:
    """Canned readings for trying the display with no Nightscout at all."""

    def __init__(self, mgdl: int = 112, minutes_ago: int = 3, direction: str = "Flat") -> None:
        self._mgdl = mgdl
        self._minutes_ago = minutes_ago
        self._direction = direction

    def fetch_entries(self, count: int = 12) -> list:
        when = datetime.now(timezone.utc) - timedelta(minutes=self._minutes_ago)
        return [
            {
                "type": "sgv",
                "sgv": self._mgdl,
                "date": int(when.timestamp() * 1000),
                "direction": self._direction,
            }
        ]


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"{name} must be a whole number, got {raw!r}") from None


def thresholds_from_env() -> Thresholds:
    """Build thresholds from GW_* environment variables (see docs/ENV_VARS.md)."""
    try:
        return Thresholds(
            urgent_low=_int_env("GW_URGENT_LOW", 55),
            low=_int_env("GW_LOW", 70),
            high=_int_env("GW_HIGH", 180),
            urgent_high=_int_env("GW_URGENT_HIGH", 250),
            stale_after=timedelta(minutes=_int_env("GW_STALE_MINUTES", 15)),
        )
    except ValueError as exc:
        raise SystemExit(f"invalid threshold settings: {exc}") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="glucose_watch", description=DISCLAIMER)
    parser.add_argument("--demo", action="store_true", help="use canned data, no network")
    parser.add_argument("--demo-mgdl", type=int, default=112, help="glucose value for --demo")
    parser.add_argument("--demo-minutes-ago", type=int, default=3, help="reading age for --demo")
    parser.add_argument("--watch", action="store_true", help="refresh until Ctrl+C")
    parser.add_argument("--interval", type=int, default=60, help="seconds between refreshes")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thresholds = thresholds_from_env()

    if args.demo:
        source = DemoSource(mgdl=args.demo_mgdl, minutes_ago=args.demo_minutes_ago)
    else:
        url = os.environ.get("NIGHTSCOUT_URL")
        if not url:
            print("Set NIGHTSCOUT_URL (see docs/ENV_VARS.md) or use --demo.", file=sys.stderr)
            return 2
        try:
            source = NightscoutClient(url, token=os.environ.get("NIGHTSCOUT_TOKEN") or None)
        except ValueError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2

    last_good = None
    while True:
        status, error = current_status(source, datetime.now(timezone.utc), thresholds, last_good)
        if error is None:
            last_good = status
        print("\n".join(render_lines(status, error)))
        if not args.watch:
            # Exit code tells scripts (Home Assistant, cron) whether to pay attention.
            return 1 if status.level.needs_attention else 0
        print("-" * 24)
        time.sleep(max(args.interval, 15))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

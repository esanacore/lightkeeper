"""Command-line entry point: `python -m lightkeeper`.

This is the composition root, the one place that wires real settings,
the real clock, and the real Nightscout client together.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from lightkeeper import __version__
from lightkeeper.application.monitor import EntrySource, current_status, render_lines
from lightkeeper.domain.status import Thresholds
from lightkeeper.infrastructure.nightscout import NightscoutClient
from lightkeeper.infrastructure.svg_display import render_svg

DISCLAIMER = (
    "lightkeeper is a secondary, read-only display. It is not a medical device. "
    "Always confirm on the primary CGM app before acting."
)


class DemoSource:
    """Canned readings for trying the display with no Nightscout at all."""

    def __init__(self, mgdl: int = 112, minutes_ago: int = 3, direction: str = "Flat") -> None:
        """Serve one reading of `mgdl`, `minutes_ago` minutes old, with `direction`."""
        self._mgdl = mgdl
        self._minutes_ago = minutes_ago
        self._direction = direction

    def fetch_entries(self, count: int = 12) -> list[Any]:
        """Return a single Nightscout-shaped entry; `count` is ignored."""
        when = datetime.now(UTC) - timedelta(minutes=self._minutes_ago)
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
    """Build thresholds from LK_* environment variables (see docs/ENV_VARS.md)."""
    try:
        return Thresholds(
            urgent_low=_int_env("LK_URGENT_LOW", 55),
            low=_int_env("LK_LOW", 70),
            high=_int_env("LK_HIGH", 180),
            urgent_high=_int_env("LK_URGENT_HIGH", 250),
            stale_after=timedelta(minutes=_int_env("LK_STALE_MINUTES", 15)),
        )
    except ValueError as exc:
        raise SystemExit(f"invalid threshold settings: {exc}") from None


def write_svg(path: str, lines: list[str], written_at: datetime | None = None) -> None:
    """Write the screen as SVG, replacing the file in one step.

    Writing to a temporary file and renaming means a dashboard reading the
    image never sees a half-written file. The optional `written_at` stamp
    lets a viewer tell a live writer from a dead one (see HAZ-011).
    """
    target = Path(path)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(render_svg(lines, written_at=written_at), encoding="utf-8")
    os.replace(temp, target)


def build_parser() -> argparse.ArgumentParser:
    """Command-line options for `python -m lightkeeper`."""
    parser = argparse.ArgumentParser(prog="lightkeeper", description=DISCLAIMER)
    parser.add_argument("--demo", action="store_true", help="use canned data, no network")
    parser.add_argument("--demo-mgdl", type=int, default=112, help="glucose value for --demo")
    parser.add_argument("--demo-minutes-ago", type=int, default=3, help="reading age for --demo")
    parser.add_argument("--watch", action="store_true", help="refresh until Ctrl+C")
    parser.add_argument("--interval", type=int, default=60, help="seconds between refreshes")
    parser.add_argument(
        "--svg", metavar="PATH", help="also write the screen as an SVG image to PATH"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run once (or with --watch, until stopped) and return the exit code.

    0 means fresh and in range, 1 means someone should look, 2 means bad configuration.
    """
    args = build_parser().parse_args(argv)
    thresholds = thresholds_from_env()

    if args.demo:
        source: EntrySource = DemoSource(mgdl=args.demo_mgdl, minutes_ago=args.demo_minutes_ago)
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
        now = datetime.now(UTC)
        status, error = current_status(source, now, thresholds, last_good)
        if error is None:
            last_good = status
        lines = render_lines(status, error)
        # flush=True: under systemd stdout is block-buffered, and a buffered
        # screen that only appears hours later is useless in `journalctl -f`.
        print("\n".join(lines), flush=True)
        if args.svg:
            try:
                write_svg(args.svg, lines, written_at=now)
            except OSError as exc:
                # A full disk or a locked file must not kill the watch loop
                # (HAZ-011); the next cycle retries. Run-once reports it.
                print(f"Could not write {args.svg}: {exc}", file=sys.stderr, flush=True)
                if not args.watch:
                    return 2
        if not args.watch:
            # Exit code tells scripts (Home Assistant, cron) whether to pay attention.
            return 1 if status.level.needs_attention else 0
        print("-" * 24, flush=True)
        try:
            time.sleep(max(args.interval, 15))
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

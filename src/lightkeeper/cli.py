"""Command-line entry point: `python -m lightkeeper`.

This is the composition root, the one place that wires real settings,
the real clock, and the real Nightscout client together.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from lightkeeper import __version__
from lightkeeper.application.monitor import EntrySource, current_status, render_lines
from lightkeeper.application.status_payload import status_payload
from lightkeeper.domain.status import Thresholds
from lightkeeper.infrastructure.home_assistant import HomeAssistantPublisher
from lightkeeper.infrastructure.mqtt import MqttError, MqttPublisher
from lightkeeper.infrastructure.nightscout import NightscoutClient
from lightkeeper.infrastructure.svg_display import render_svg
from lightkeeper.infrastructure.systemd_notify import SystemdNotifier

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


_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw == "":
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


def home_assistant_from_env(
    interval_seconds: int, thresholds: Thresholds
) -> HomeAssistantPublisher | None:
    """Build the Home Assistant publisher from LK_MQTT_* variables, or None when unset.

    Raises ValueError for an unusable configuration (see docs/ENV_VARS.md).
    """
    host = os.environ.get("LK_MQTT_HOST", "").strip()
    if not host:
        return None
    tls = _bool_env("LK_MQTT_TLS", True)
    port = _int_env("LK_MQTT_PORT", 8883 if tls else 1883)
    node_id = os.environ.get("LK_MQTT_NODE_ID") or "lightkeeper"
    mqtt = MqttPublisher(
        host,
        port,
        client_id=f"lightkeeper-{node_id}",
        username=os.environ.get("LK_MQTT_USERNAME") or None,
        password=os.environ.get("LK_MQTT_PASSWORD") or None,
        tls=tls,
    )
    return HomeAssistantPublisher(
        mqtt,
        interval_seconds=interval_seconds,
        stale_seconds=int(thresholds.stale_after.total_seconds()),
        node_id=node_id,
        discovery_prefix=os.environ.get("LK_MQTT_DISCOVERY_PREFIX") or "homeassistant",
    )


def write_json(path: str, payload: dict[str, Any]) -> None:
    """Write the status as JSON, replacing the file in one step (like write_svg)."""
    target = Path(path)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, target)


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
    parser.add_argument(
        "--json", metavar="PATH", help="also write the status as JSON to PATH (for dashboards)"
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

    interval = max(args.interval, 15)
    try:
        home_assistant = home_assistant_from_env(interval, thresholds)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    notifier = SystemdNotifier()
    notifier.ready("starting")
    try:
        return _run(args, source, thresholds, interval, home_assistant, notifier)
    finally:
        notifier.stopping()
        if home_assistant is not None:
            # A --watch loop that stops marks the entities unavailable; a
            # one-shot run leaves them for the next run (HAZ-013).
            home_assistant.finish(offline=args.watch)


def _run(
    args: argparse.Namespace,
    source: EntrySource,
    thresholds: Thresholds,
    interval: int,
    home_assistant: HomeAssistantPublisher | None,
    notifier: SystemdNotifier,
) -> int:
    """Run the refresh loop: fetch, show, write, publish, sleep."""
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
        payload = status_payload(status, error, now)
        outputs: list[tuple[str, functools.partial[None]]] = []
        if args.svg:
            outputs.append((args.svg, functools.partial(write_svg, args.svg, lines, now)))
        if args.json:
            outputs.append((args.json, functools.partial(write_json, args.json, payload)))
        for target, write in outputs:
            try:
                write()
            except OSError as exc:
                # A full disk or a locked file must not kill the watch loop
                # (HAZ-011); the next cycle retries. Run-once reports it.
                print(f"Could not write {target}: {exc}", file=sys.stderr, flush=True)
                if not args.watch:
                    return 2
        if home_assistant is not None:
            try:
                home_assistant.publish(payload)
            except MqttError as exc:
                # Never stops the display. The broker's will and expire_after
                # make Home Assistant show unavailable meanwhile (HAZ-013).
                print(f"Home Assistant publish failed: {exc}", file=sys.stderr, flush=True)
        # A finished cycle pets the systemd watchdog; a hung one does not, and
        # systemd restarts the service instead of leaving a frozen screen (HAZ-002).
        notifier.alive(status.level.value + (", Nightscout unreachable" if error else ""))
        if not args.watch:
            # Exit code tells scripts (Home Assistant, cron) whether to pay attention.
            return 1 if status.level.needs_attention else 0
        print("-" * 24, flush=True)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

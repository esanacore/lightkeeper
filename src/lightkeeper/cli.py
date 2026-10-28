"""Command-line entry point: `python -m lightkeeper`.

This is the composition root, the one place that wires real settings,
the real clock, and the real Nightscout client together. The settings
themselves are read and checked in `lightkeeper.config`; the names that
used to live here are re-exported.

Honest output (FR-006): stdout is exactly the vector lines, so pipes, cron
and systemd read what they always have; only an interactive terminal running
--watch gets the logbook frame. What went wrong, and which setting to check,
goes to stderr, redacted, once per change of what failed. An interrupted or
misconfigured run never reports "fresh and in range": it exits 130 or 2.
"""

from __future__ import annotations

import argparse
import errno
import functools
import json
import os
import shutil
import sys
import textwrap
import time
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from lightkeeper import __version__
from lightkeeper.application.monitor import EntrySource, current_status, render_lines
from lightkeeper.application.status_payload import status_payload
from lightkeeper.config import (
    DEMO_MGDL,
    DEMO_MINUTES_AGO,
    DEMO_TREND,
    ConfigError,
    DemoSource,
    home_assistant_from_env,
    source_from_env,
    thresholds_from_env,
)
from lightkeeper.domain.glucose import Trend
from lightkeeper.domain.status import Thresholds
from lightkeeper.infrastructure import terminal_view
from lightkeeper.infrastructure.epaper_bitmap import Bitmap, render_bitmap, stamp_text
from lightkeeper.infrastructure.home_assistant import HomeAssistantPublisher
from lightkeeper.infrastructure.mqtt import MqttError
from lightkeeper.infrastructure.nightscout import NightscoutClient, NightscoutError
from lightkeeper.infrastructure.panel_profiles import DEFAULT_PROFILE, PanelProfile, resolve
from lightkeeper.infrastructure.svg_display import render_svg
from lightkeeper.infrastructure.systemd_notify import SystemdNotifier

__all__ = [
    "DISCLAIMER",
    "ConfigError",
    "DemoSource",
    "build_parser",
    "describe_write_error",
    "home_assistant_from_env",
    "main",
    "source_from_env",
    "thresholds_from_env",
    "write_bmp",
    "write_json",
    "write_png",
    "write_svg",
]

DISCLAIMER = (
    "lightkeeper is a secondary, read-only display. It is not a medical device. "
    "Always confirm on the primary CGM app before acting."
)

MIN_INTERVAL_SECONDS = 15
DEFAULT_INTERVAL_SECONDS = 60
SEPARATOR = "-" * 24  # between --watch cycles on plain output
EXIT_INTERRUPTED = 130  # 128 + SIGINT, as shells report Ctrl+C
ENV_VARS_URL = "https://github.com/esanacore/lightkeeper/blob/main/docs/ENV_VARS.md"
TREND_NAMES = [trend.value for trend in Trend]
_DEMO_ONLY = ("demo_mgdl", "demo_minutes_ago", "demo_trend")

EPILOG = f"""\
examples:
  lightkeeper --demo                    canned reading, no network
  lightkeeper --demo --demo-mgdl 62 --demo-trend SingleDown
  lightkeeper                           read Nightscout once
  lightkeeper --watch --interval 60     refresh until Ctrl+C
  lightkeeper --watch --svg screen.svg --json status.json
  lightkeeper --bmp panel.bmp --panel 800x480

exit codes:
  0    fresh and in range
  1    someone should look: low, high, STALE, NO DATA, or Nightscout unreachable
  2    configuration error: a setting or option that cannot be used, or a
       file a one-shot run could not write
  130  a one-shot run stopped with Ctrl+C (--watch stopped that way exits 0)

environment:
  NIGHTSCOUT_URL      your Nightscout site, https only (not needed with --demo)
  NIGHTSCOUT_TOKEN    a token with the readable role, never the API secret
  LK_URGENT_LOW, LK_LOW, LK_HIGH, LK_URGENT_HIGH, LK_STALE_MINUTES
                      the display thresholds in mg/dL, and minutes until STALE
  LK_MQTT_HOST        turns on Home Assistant over MQTT (more LK_MQTT_* settings)
  NO_COLOR            set to anything: no color in the --watch frame

every variable: {ENV_VARS_URL}
"""


def write_json(path: str, payload: dict[str, Any]) -> None:
    """Write the status as JSON, replacing the file in one step (like write_svg)."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _replace(Path(path), lambda temp: temp.write_text(text, encoding="utf-8"))


def write_svg(path: str, lines: list[str], written_at: datetime | None = None) -> None:
    """Write the screen as SVG, replacing the file in one step.

    Writing to a temporary file and renaming means a dashboard reading the
    image never sees a half-written file. The optional `written_at` stamp
    lets a viewer tell a live writer from a dead one (see HAZ-011).
    """
    svg = render_svg(lines, written_at=written_at)
    _replace(Path(path), lambda temp: temp.write_text(svg, encoding="utf-8"))


def write_png(path: str, bitmap: Bitmap) -> None:
    """Write the panel pixels as a 1-bit PNG, replacing the file in one step."""
    data = bitmap.to_png()
    _replace(Path(path), lambda temp: temp.write_bytes(data))


def write_bmp(path: str, bitmap: Bitmap) -> None:
    """Write the panel pixels as a 1-bit BMP, replacing the file in one step."""
    data = bitmap.to_bmp()
    _replace(Path(path), lambda temp: temp.write_bytes(data))


def _replace(target: Path, write: Callable[[Path], object]) -> None:
    """Write through a temporary file beside `target`, then rename it into place.

    A reader never sees a half-written file. A failed write removes the
    temporary file and raises the OSError for the caller to report.
    """
    temp = target.with_name(target.name + ".tmp")
    try:
        write(temp)
        os.replace(temp, target)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass  # the folder itself is the problem; the caller reports that
        raise


def panel_image(lines: list[str], profile: PanelProfile, written_at: datetime) -> Bitmap:
    """Draw the panel pixels, stamped with the local `HH:MM` of `written_at` (HAZ-014)."""
    return render_bitmap(lines, profile.width, profile.height, stamp=stamp_text(written_at))


def describe_write_error(exc: OSError, target: str) -> str:
    """Say in plain words why `target` could not be written.

    Never the temporary file's name or a raw error number: the person only
    knows the path they asked for.
    """
    folder = Path(target).parent
    if isinstance(exc, FileNotFoundError) and not folder.is_dir():
        return f"the folder {folder} does not exist"
    if isinstance(exc, PermissionError):
        return "permission denied"
    if isinstance(exc, IsADirectoryError):
        return f"{target} is a folder"
    if isinstance(exc, NotADirectoryError):
        return f"part of the folder {folder} is a file, not a folder"
    if exc.errno == errno.ENOSPC:
        return "the disk is full"
    return (exc.strerror or type(exc).__name__).lower()


def _trend(text: str) -> str:
    """Accept a Nightscout trend name in any case; argparse then checks the choice."""
    return next((name for name in TREND_NAMES if name.lower() == text.lower()), text)


def _panel(text: str) -> PanelProfile:
    try:
        return resolve(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def build_parser() -> argparse.ArgumentParser:
    """Command-line options for `python -m lightkeeper`."""
    parser = argparse.ArgumentParser(
        prog="lightkeeper",
        description=textwrap.fill(DISCLAIMER, 79),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--demo", action="store_true", help="use canned data, no network")
    parser.add_argument(
        "--demo-mgdl",
        type=int,
        metavar="MGDL",
        help=f"glucose value for --demo (default {DEMO_MGDL})",
    )
    parser.add_argument(
        "--demo-minutes-ago",
        type=int,
        metavar="MINUTES",
        help=f"reading age for --demo (default {DEMO_MINUTES_AGO})",
    )
    parser.add_argument(
        "--demo-trend",
        type=_trend,
        choices=TREND_NAMES,
        metavar="TREND",
        help=f"trend for --demo: {', '.join(TREND_NAMES)} (default {DEMO_TREND})",
    )
    parser.add_argument("--watch", action="store_true", help="refresh until Ctrl+C")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        metavar="SECONDS",
        help=(
            f"seconds between refreshes (default {DEFAULT_INTERVAL_SECONDS}, "
            f"minimum {MIN_INTERVAL_SECONDS})"
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="no color in the interactive --watch frame (as NO_COLOR does)",
    )
    parser.add_argument(
        "--svg", metavar="PATH", help="also write the screen as an SVG image to PATH"
    )
    parser.add_argument(
        "--json", metavar="PATH", help="also write the status as JSON to PATH (for dashboards)"
    )
    parser.add_argument(
        "--png",
        metavar="PATH",
        help="also write the panel pixels as a 1-bit PNG to PATH, stamped with the time",
    )
    parser.add_argument(
        "--bmp",
        metavar="PATH",
        help="also write the panel pixels as a 1-bit BMP to PATH, stamped with the time",
    )
    parser.add_argument(
        "--panel",
        type=_panel,
        default=resolve(DEFAULT_PROFILE),
        metavar="PROFILE",
        help=(
            "panel for --png and --bmp: a profile name (waveshare_2in9, waveshare_1in54, "
            "waveshare_2in13, waveshare_4in2, waveshare_7in5 or trmnl, kindle) or a size "
            f"like 800x480 (default {DEFAULT_PROFILE})"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


class _RecordingSource:
    """Passes fetches through and keeps the last exception, for the diagnostics.

    current_status turns any failure into a STALE or NO DATA screen and a
    message; this wrapper lets the CLI also see what failed, so monitor.py
    stays as it is.
    """

    def __init__(self, source: EntrySource) -> None:
        self._source = source
        self.last_error: Exception | None = None

    def fetch_entries(self, count: int = 12) -> list[Any]:
        try:
            entries = self._source.fetch_entries(count)
        except Exception as exc:
            self.last_error = exc
            raise
        self.last_error = None
        return entries


class _Diagnostics:
    """One stderr line per change of what failed, and one on recovery.

    Advice about settings, never screen text: the screen says "Nightscout
    unreachable" whatever the kind. Every line is redacted, and a failure
    that repeats every cycle is reported once, not once a minute.
    """

    def __init__(self, secrets: list[str]) -> None:
        self._secrets = [s for s in secrets if s]
        self._kind: str | None = None

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            for form in (secret, urllib.parse.quote(secret, safe=""), repr(secret)[1:-1]):
                text = text.replace(form, "***")
        return text

    def update(self, error: str | None, exc: Exception | None) -> str | None:
        """Return the line to print for this cycle, or None when nothing changed."""
        if error is None:
            if self._kind is None:
                return None
            self._kind = None
            return "lightkeeper: Nightscout reachable again"
        if isinstance(exc, NightscoutError):
            kind, advice = exc.kind, exc.hint
        else:
            kind, advice = "other", f"could not read the readings: {error}"
        if kind == self._kind:
            return None
        self._kind = kind
        return self._redact(f"lightkeeper: {advice}")


class _Screen:
    """Shows each cycle: the plain vector lines, or the logbook frame.

    The frame is only for --watch on an interactive terminal whose TERM is
    not `dumb`. Everything else gets exactly the vector lines.
    """

    def __init__(self, args: argparse.Namespace, stream: TextIO, environ: Mapping[str, str]):
        self.framed = bool(args.watch) and stream.isatty()
        self.framed = self.framed and environ.get("TERM", "").strip().lower() != "dumb"
        self._escapes = self.framed and terminal_view.enable_vt()
        self._color = not args.no_color and not environ.get("NO_COLOR")
        self._first = True

    def show(self, lines: list[str], now: datetime, interval: int) -> None:
        # flush=True: under systemd stdout is block-buffered, and a buffered
        # screen that only appears hours later is useless in `journalctl -f`.
        if not self.framed:
            print("\n".join(lines), flush=True)
            return
        frame = terminal_view.render_frame(
            lines,
            now,
            interval,
            escapes=self._escapes,
            color=self._color,
            columns=shutil.get_terminal_size().columns,
            first=self._first,
        )
        self._first = False
        sys.stdout.write(frame)
        sys.stdout.flush()

    def end_cycle(self) -> None:
        if not self.framed:
            print(SEPARATOR, flush=True)


def _check_demo_flags(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Refuse the demo options without --demo: canned data must never look real."""
    given = [
        f"--{name.replace('_', '-')}" for name in _DEMO_ONLY if getattr(args, name) is not None
    ]
    if given and not args.demo:
        verb = "needs" if len(given) == 1 else "need"
        parser.error(
            f"{' and '.join(given)} {verb} --demo: canned readings are shown only with --demo"
        )


def main(argv: list[str] | None = None) -> int:
    """Run once (or with --watch, until stopped) and return the exit code.

    0 means fresh and in range, 1 means someone should look, 2 means bad
    configuration, and 130 means a one-shot run was stopped with Ctrl+C
    (never 0, which would read as fresh and in range to cron or Home
    Assistant). A --watch loop stopped with Ctrl+C exits 0.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    _check_demo_flags(parser, args)
    interval = max(args.interval, MIN_INTERVAL_SECONDS)
    try:
        thresholds = thresholds_from_env()
        # NightscoutClient is looked up here, at call time, so tests can stand in for it.
        source = source_from_env(args, client_factory=NightscoutClient)
        home_assistant = home_assistant_from_env(interval, thresholds)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    notifier = SystemdNotifier()
    notifier.ready("starting")
    try:
        return _run(args, source, thresholds, interval, home_assistant, notifier)
    except KeyboardInterrupt:
        if args.watch:
            return 0
        print("lightkeeper: stopped", file=sys.stderr, flush=True)
        return EXIT_INTERRUPTED
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
    """Run the refresh loop: fetch, show, advise, write, publish, sleep."""
    recorder = _RecordingSource(source)
    diagnostics = _Diagnostics([os.environ.get("NIGHTSCOUT_TOKEN", "").strip()])
    screen = _Screen(args, sys.stdout, os.environ)
    last_good = None
    while True:
        now = datetime.now(UTC)
        status, error = current_status(recorder, now, thresholds, last_good)
        if error is None:
            last_good = status
        lines = render_lines(status, error)
        screen.show(lines, now, interval)
        advice = diagnostics.update(error, recorder.last_error)
        if advice is not None:
            print(advice, file=sys.stderr, flush=True)
        payload = status_payload(status, error, now)
        outputs: list[tuple[str, Callable[[], None]]] = []
        if args.svg:
            outputs.append((args.svg, functools.partial(write_svg, args.svg, lines, now)))
        if args.json:
            outputs.append((args.json, functools.partial(write_json, args.json, payload)))
        if args.png or args.bmp:
            bitmap = panel_image(lines, args.panel, now)
            if args.png:
                outputs.append((args.png, functools.partial(write_png, args.png, bitmap)))
            if args.bmp:
                outputs.append((args.bmp, functools.partial(write_bmp, args.bmp, bitmap)))
        for target, write in outputs:
            try:
                write()
            except OSError as exc:
                # A full disk or a locked file must not kill the watch loop
                # (HAZ-011); the next cycle retries. Run-once reports it.
                reason = describe_write_error(exc, target)
                print(f"Could not write {target}: {reason}", file=sys.stderr, flush=True)
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
        screen.end_cycle()
        time.sleep(interval)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

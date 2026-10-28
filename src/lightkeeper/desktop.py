"""Desktop glance window: `python -m lightkeeper.desktop` (FR-018).

A composition root, with cli.py and config.py, outside the layers: this is
where the settings, the clock, the fetch worker and tkinter are wired to the
glance (application/glance.py) and the window (infrastructure/tk_window.py).
The window shows the real e-paper panel, so it is a secondary, read-only
display like every other: it is not a medical device, and the primary CGM app
is what to act on.

Fetches run on a worker thread, never on Tk's: a slow Nightscout must not
freeze the window. Their answers come back through a queue that Tk's thread
polls with after(), every POLL_MS. A second timer re-ages the screen from the
last good reading on its own schedule, so the window goes STALE on time with
no fetch at all, and a wall-clock jump (sleep and wake) or a hung fetch is
caught at the next poll (glance.py says how).

tkinter is imported only when the window opens, so the CLI and the Pi never
load it. With no tkinter at all, a one-line hint says what to install; a
setting that cannot be used prints the plain message; both exit 2 before any
window opens. `q` and the close box exit 0, and Ctrl+C in the terminal that
started the window exits 130, as a stopped one-shot run of the CLI does.
Nothing here writes to stdout, and stderr is used only when there is one: a
window is exactly what gets started with pythonw, where both are None.
"""

from __future__ import annotations

import argparse
import queue
import sys
import textwrap
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from lightkeeper.application.glance import Glance
from lightkeeper.application.monitor import EntrySource
from lightkeeper.config import source_from_env, thresholds_from_env
from lightkeeper.infrastructure import tk_window
from lightkeeper.infrastructure.nightscout import NightscoutClient
from lightkeeper.infrastructure.panel_profiles import ALIASES, DEFAULT_PROFILE, PROFILES, resolve

DESCRIPTION = (
    "A desktop window showing the real e-paper panel. It is a secondary, read-only "
    "display and not a medical device: always confirm on the primary CGM app before acting."
)
EPILOG = """\
keys:
  r    check Nightscout now
  t    switch between the panel's pixels and its lines as text
  q    quit (as the close box does)

examples:
  python -m lightkeeper.desktop --demo              canned reading, no network
  python -m lightkeeper.desktop --scale 3 --on-top
  python -m lightkeeper.desktop --panel 800x480 --theme dark

exit codes:
  0    the window was closed
  2    a setting that cannot be used, no tkinter, or no display to open a window on
  130  stopped with Ctrl+C in the terminal that started it

settings come from the same environment variables as the CLI (NIGHTSCOUT_URL,
NIGHTSCOUT_TOKEN, LK_*); see docs/ENV_VARS.md.
"""
TK_HINT = (
    "lightkeeper: the window needs Tk, which this Python does not have: install "
    "python3-tk (for example, sudo apt install python3-tk) or a Python that includes Tk"
)
INTERVAL_SECONDS = 60  # between fetches, as the CLI's default
POLL_MS = 250  # how often Tk's thread looks for answers, a jump or a hung fetch
SCALES = (2, 3)
THEMES = ("auto", tk_window.LIGHT_THEME, tk_window.DARK_THEME)
EXIT_INTERRUPTED = 130  # 128 + SIGINT, as shells report Ctrl+C

Outcome = list[Any] | Exception


def _now() -> datetime:
    return datetime.now(UTC)


def _warn(text: str) -> None:
    """Print one line on stderr; with no stderr at all, nowhere, and never on stdout.

    print() to a stderr of None (pythonw, a gui-script launcher) would fall
    back to stdout.
    """
    if sys.stderr is not None:
        print(text, file=sys.stderr, flush=True)


class Worker:
    """One daemon thread that runs fetches off Tk's thread and queues what they returned.

    Daemon, so a fetch that hangs never keeps the process alive after the
    window closes. An exception a fetch raises is queued as its answer, with
    its traceback dropped; Tk's thread keeps only its message (current_status).
    """

    def __init__(self) -> None:
        """Start the thread; it waits for work."""
        self._jobs: queue.SimpleQueue[Callable[[], list[Any]] | None] = queue.SimpleQueue()
        self._done: queue.SimpleQueue[Outcome] = queue.SimpleQueue()
        self._thread = threading.Thread(target=self._run, name="lightkeeper-fetch", daemon=True)
        self._thread.start()

    def submit(self, fetch: Callable[[], list[Any]]) -> None:
        """Queue `fetch` to run on the worker thread; never runs it here."""
        self._jobs.put(fetch)

    def finished(self) -> list[Outcome]:
        """Return every answer that came back since the last call, oldest first."""
        answers = []
        while True:
            try:
                answers.append(self._done.get_nowait())
            except queue.Empty:
                return answers

    def close(self) -> None:
        """Let the thread end after the fetch it is running, if any; does not wait for it."""
        self._jobs.put(None)

    def _run(self) -> None:
        while (fetch := self._jobs.get()) is not None:
            try:
                answer: Outcome = fetch()
            except Exception as exc:  # any failure is an answer: current_status degrades it
                answer = exc.with_traceback(None)
            self._done.put(answer)


class Session:
    """Runs the glance on Tk's thread: the poll, the re-age timer, and the keys."""

    def __init__(
        self, glance: Glance, source: EntrySource, clock: Callable[[], datetime] = _now
    ) -> None:
        """Hold `glance` and `source`; the window and the worker come with `start`.

        The window needs this session's `refresh` and `fail` before it opens,
        and the worker thread starts only once the window has opened.
        """
        self._glance = glance
        self._source = source
        self._clock = clock
        self._window: Any = None
        self._worker: Any = None
        self._redraw_job: Any = None
        self.failure: BaseException | None = None  # what a Tk callback raised, if anything

    def start(self, window: Any, worker: Any) -> None:
        """Show the first screen (NO DATA until an answer) in `window`, then start polling.

        `window` is a GlanceWindow and `worker` a Worker, or stand-ins for them.
        """
        self._window = window
        self._worker = worker
        self._redraw()
        self._poll()

    def refresh(self) -> None:
        """Check Nightscout now (the `r` key), unless a check is running already."""
        now = self._clock()
        self._glance.refresh(now)
        self._fetch_if_due(now)

    def fail(self, error: BaseException) -> None:
        """Stop the window on an exception from a Tk callback; main() then reports it."""
        if self.failure is None:
            self.failure = error
        self._window.quit()

    def _poll(self) -> None:
        now = self._clock()
        changed = False
        for answer in self._worker.finished():
            self._glance.fetch_finished(answer, now)
            changed = True
        if self._glance.poll(now):
            changed = True
        self._fetch_if_due(now)
        if changed:
            self._redraw()
        self._window.after(POLL_MS, self._poll)

    def _fetch_if_due(self, now: datetime) -> None:
        if self._glance.fetch_due(now):
            self._glance.fetch_started(now)
            self._worker.submit(self._source.fetch_entries)

    def _redraw(self) -> None:
        """Show the screen for now, and set the re-age timer for the next change."""
        if self._redraw_job is not None:
            self._window.after_cancel(self._redraw_job)
        now = self._clock()
        view = self._glance.view(now)
        self._window.show(view.lines, view.title, now)
        self._redraw_job = self._window.after(self._glance.next_redraw_ms(now), self._timer)

    def _timer(self) -> None:
        self._redraw_job = None  # this one has fired; nothing to cancel
        self._redraw()


def build_parser() -> argparse.ArgumentParser:
    """Command-line options for `python -m lightkeeper.desktop`."""
    parser = argparse.ArgumentParser(
        prog="python -m lightkeeper.desktop",
        description=textwrap.fill(DESCRIPTION, 79),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--demo", action="store_true", help="use a canned reading, no network")
    parser.add_argument(
        "--scale",
        type=int,
        choices=SCALES,
        default=SCALES[0],
        help=(
            "whole-number zoom for the panel's pixels, in 96 dpi pixels: on a display "
            f"scaled to 200%%, each panel pixel is twice as many device pixels "
            f"(default {SCALES[0]})"
        ),
    )
    names = [*PROFILES, *(f"{alias} (= {name})" for alias, name in ALIASES.items())]
    parser.add_argument(
        "--panel",
        default=DEFAULT_PROFILE,
        metavar="PROFILE",
        help=f"panel to show: {', '.join(names)}, or a size like 800x480 "
        f"(default {DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--on-top", action="store_true", help="keep the window above other windows"
    )
    parser.add_argument(
        "--theme",
        choices=THEMES,
        default=THEMES[0],
        help="light, dark, or auto: the system's app theme on Windows, else light (default auto)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Open the window and run it until it is closed; return the exit code.

    0 when closed with `q` or the close box, 2 for a setting that cannot be
    used or no way to open a window, and 130 for Ctrl+C. An unexpected error
    in the window closes it and is raised again: a window that has stopped
    updating must not stay on screen looking alive.
    """
    try:
        return _start(build_parser().parse_args(argv))
    except KeyboardInterrupt:
        _warn("lightkeeper: stopped")
        return EXIT_INTERRUPTED


def _start(args: argparse.Namespace) -> int:
    """Check every setting, then open the window; exit 2 before it opens if one is unusable."""
    try:
        profile = resolve(args.panel)
        thresholds = thresholds_from_env()
        # NightscoutClient is looked up here, at call time, so tests can stand in for it.
        source = source_from_env(args, client_factory=NightscoutClient)
    except ValueError as exc:  # ConfigError, naming the setting, or the panel's own check
        _warn(f"Configuration error: {exc}")
        return 2
    try:
        import tkinter
    except ImportError:
        _warn(TK_HINT)
        return 2

    theme = tk_window.system_theme() if args.theme == "auto" else args.theme
    # Before the window opens: Tk reads the display's density once, at startup.
    tk_window.use_device_pixels()
    session = Session(
        Glance(thresholds, timedelta(seconds=INTERVAL_SECONDS), _now()), source, _now
    )
    try:
        window = tk_window.GlanceWindow(
            tkinter,
            profile.width,
            profile.height,
            args.scale,
            theme,
            on_top=args.on_top,
            on_refresh=session.refresh,
            on_error=session.fail,
        )
    except tkinter.TclError as exc:  # no display to open a window on
        _warn(f"lightkeeper: could not open the window: {exc}")
        return 2
    try:
        worker = Worker()
        try:
            session.start(window, worker)
            window.mainloop()
        finally:
            worker.close()
    finally:
        # Whatever stopped it, the window goes: a window that no longer updates
        # must not stay on screen looking alive.
        window.destroy()
    if session.failure is not None:
        # Ctrl+C during a callback goes back to main() as 130; anything else is a bug,
        # raised with the window already gone.
        raise session.failure
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

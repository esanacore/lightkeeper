"""FR-018, HAZ-002, HAZ-008: `python -m lightkeeper.desktop` opens the glance window honestly.

main() runs here with a fake source and FakeTk (tests/test_tk_window.py) in
sys.modules as tkinter, so no display is needed. The window starts on NO DATA
until the first answer; every fetch runs on the worker thread, never on Tk's,
and a fetch given up on leaves its thread behind; the ticker thread keeps the
poll going when Tk's wall-clock timers stall; a setting that cannot be used, a
panel too large for the screen, or no tkinter, exits 2; `q` exits 0 and Ctrl+C
130; and the CLI never loads tkinter at all.
"""

import os
import re
import subprocess
import sys
import threading
import time
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lightkeeper import desktop
from lightkeeper.application.glance import Glance
from lightkeeper.domain.status import Thresholds
from lightkeeper.infrastructure import tk_window
from lightkeeper.infrastructure.epaper_bitmap import render_bitmap, stamp_text
from lightkeeper.infrastructure.ppm import DARK, LIGHT, to_ppm
from tests.helpers import NOW, FakeSource, entry
from tests.test_tk_window import NO_REAL_TK, FakeTclError, FakeTk, real_tkinter, run_real_tk

ROOT = Path(__file__).resolve().parent.parent
NO_DATA_TITLE = "NO DATA - Check sensor and phone - checking Nightscout... - Lightkeeper"
NO_DATA = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
WAIT_SECONDS = 5  # the most a test waits for the worker thread, in real time


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in [
        "NIGHTSCOUT_URL",
        "NIGHTSCOUT_TOKEN",
        "LK_URGENT_LOW",
        "LK_LOW",
        "LK_HIGH",
        "LK_URGENT_HIGH",
        "LK_STALE_MINUTES",
    ]:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def tk(monkeypatch):
    """FakeTk as the tkinter module; the system theme and DPI calls recorded, not made."""
    fake = FakeTk()
    monkeypatch.setitem(sys.modules, "tkinter", fake)
    fake.system_calls = []
    monkeypatch.setattr(
        tk_window, "system_theme", lambda: fake.system_calls.append("theme") or "light"
    )
    monkeypatch.setattr(
        tk_window, "use_device_pixels", lambda: fake.system_calls.append("pixels") or True
    )
    return fake


def run_until(root, condition, what):
    """Step the fake main loop until `condition()`, giving the worker real time to answer."""
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        root.step()
        time.sleep(0.001)


class GatedSource:
    """Answers only once the test opens the gate, and notes which thread asked."""

    def __init__(self, entries):
        self.entries = entries
        self.gate = threading.Event()
        self.threads = []
        self.timed_out = False

    def fetch_entries(self, count=12):
        self.threads.append(threading.current_thread())
        if not self.gate.wait(WAIT_SECONDS):
            self.timed_out = True
        return self.entries


def use_source(monkeypatch, source):
    monkeypatch.setattr(desktop, "source_from_env", lambda args, client_factory: source)


def fresh_entries():
    return [entry(mgdl=112, minutes_ago=0) | {"date": int(time.time() * 1000) - 180_000}]


# --- the first screen, and the worker -----------------------------------------------------


def test_fr018_window_shows_no_data_before_the_first_fetch(tk, monkeypatch):
    source = GatedSource(fresh_entries())
    use_source(monkeypatch, source)
    seen = {}

    def driver(root):
        # The first screen is up and the fetch is out, but has not answered.
        seen["first"] = root.titles[1]
        seen["first_photo"] = tk.photos[0].data
        run_until(root, lambda: source.threads, "the fetch to start")
        seen["while_waiting"] = root.titles[-1]
        source.gate.set()
        run_until(root, lambda: root.titles[-1].startswith("IN RANGE"), "the answer")
        root.press("q")

    tk.driver = driver
    assert desktop.main([]) == 0
    assert seen["first"] == seen["while_waiting"] == NO_DATA_TITLE
    assert seen["first_photo"].startswith(b"P6\n592 256\n255\n")
    assert re.fullmatch(
        r"IN RANGE - 3 min ago - checked \d\d:\d\d - Lightkeeper", tk.roots[0].titles[-1]
    )
    assert not source.timed_out


def test_fr018_fetch_runs_on_the_worker_thread_never_inline(tk, monkeypatch):
    source = GatedSource(fresh_entries())
    source.gate.set()
    use_source(monkeypatch, source)

    def driver(root):
        run_until(root, lambda: root.titles[-1].startswith("IN RANGE"), "the answer")
        root.press("r")  # a second check, at once
        run_until(root, lambda: len(source.threads) == 2, "the second fetch")
        root.press("q")

    tk.driver = driver
    assert desktop.main([]) == 0
    assert {thread.name for thread in source.threads} == {"lightkeeper-fetch"}
    assert threading.main_thread() not in source.threads


def test_fr018_first_screen_is_the_no_data_panel(tk, monkeypatch):
    use_source(monkeypatch, FakeSource(entries=[]))
    tk.driver = lambda root: root.press("q")
    before = datetime.now(UTC)
    assert desktop.main([]) == 0
    after = datetime.now(UTC)
    photo = tk.photos[0].data
    stamps = {stamp_text(before), stamp_text(after)}
    assert photo in {to_ppm(render_bitmap(NO_DATA, 296, 128, stamp=s), 2) for s in stamps}


def test_fr018_demo_shows_the_canned_reading(tk):
    tk.driver = lambda root: (
        run_until(root, lambda: root.titles[-1].startswith("IN RANGE"), "the demo reading"),
        root.press("q"),
    )
    assert desktop.main(["--demo"]) == 0
    assert re.fullmatch(
        r"IN RANGE - 3 min ago - checked \d\d:\d\d - Lightkeeper", tk.roots[0].titles[-1]
    )


def test_fr018_unreachable_nightscout_shows_unreachable(tk, monkeypatch):
    use_source(monkeypatch, FakeSource(error=OSError("no route to host")))
    tk.driver = lambda root: (
        run_until(root, lambda: "checked" in root.titles[-1], "the failed answer"),
        root.press("q"),
    )
    assert desktop.main([]) == 0
    assert tk.roots[0].titles[-1].startswith("NO DATA - Check sensor and phone - checked ")


def test_fr018_real_nightscout_client_gets_the_settings(tk, monkeypatch):
    """Without --demo, the source is NightscoutClient from NIGHTSCOUT_URL and the token."""
    made = []

    class Client(FakeSource):
        def __init__(self, url, token=None):
            super().__init__(entries=[])
            made.append((url, token))

    monkeypatch.setattr(desktop, "NightscoutClient", Client)
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")
    monkeypatch.setenv("NIGHTSCOUT_TOKEN", "readable-token")
    tk.driver = lambda root: root.press("q")
    assert desktop.main([]) == 0
    assert made == [("https://ns.example.com", "readable-token")]


# --- settings, and what is missing --------------------------------------------------------


def test_fr018_config_error_exits_2_before_any_window(tk, monkeypatch, capsys):
    monkeypatch.setenv("LK_LOW", "200")
    assert desktop.main(["--demo"]) == 2
    assert capsys.readouterr().err == (
        "Configuration error: LK_LOW=200 must be below LK_HIGH=180 (the default)\n"
    )
    assert tk.roots == []


def test_fr018_missing_nightscout_url_exits_2(tk, capsys):
    assert desktop.main([]) == 2
    assert "NIGHTSCOUT_URL is not set" in capsys.readouterr().err
    assert tk.roots == []


def test_fr018_unknown_panel_exits_2(tk, capsys):
    assert desktop.main(["--demo", "--panel", "etch-a-sketch"]) == 2
    assert "Configuration error: unknown panel 'etch-a-sketch'" in capsys.readouterr().err
    assert tk.roots == []


def test_fr018_missing_tkinter_exits_2_with_a_one_line_hint(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "tkinter", None)  # import tkinter raises ImportError
    assert desktop.main(["--demo"]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "python3-tk" in err
    assert err == desktop.TK_HINT + "\n"


def test_fr018_no_display_exits_2(tk, monkeypatch, capsys):
    tk.error = FakeTclError("no display name and no $DISPLAY environment variable")
    assert desktop.main(["--demo"]) == 2
    assert capsys.readouterr().err == (
        "lightkeeper: could not open the window: no display name and no $DISPLAY "
        "environment variable\n"
    )


@pytest.mark.parametrize("argv", [["--scale", "4"], ["--scale", "2.5"], ["--theme", "sepia"]])
def test_fr018_unusable_options_exit_2(tk, argv, capsys):
    with pytest.raises(SystemExit) as exit_info:
        desktop.main(argv)
    assert exit_info.value.code == 2
    assert tk.roots == []


def test_fr018_help_names_the_keys_and_the_exit_codes(capsys):
    with pytest.raises(SystemExit) as exit_info:
        desktop.main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    for text in ("r    check Nightscout now", "130  stopped with Ctrl+C", "not a medical device"):
        assert text in out


def test_fr018_no_stdout_or_stderr_is_fine(tk, monkeypatch):
    """Under pythonw both are None: nothing may write to them, or fall back to stdout."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert desktop.main([]) == 2  # NIGHTSCOUT_URL missing, said nowhere
    tk.driver = lambda root: root.press("q")
    assert desktop.main(["--demo"]) == 0
    monkeypatch.setitem(sys.modules, "tkinter", None)
    assert desktop.main(["--demo"]) == 2


def test_fr018_lightkeeper_window_is_a_gui_script_for_main():
    """The installed launcher runs with no console (pythonw on Windows), which main() allows."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["gui-scripts"] == {"lightkeeper-window": "lightkeeper.desktop:main"}
    assert "lightkeeper-window" not in project["scripts"]


# --- quitting -----------------------------------------------------------------------------


def test_fr018_q_quits_cleanly_with_exit_0(tk):
    tk.driver = lambda root: root.press("q")
    assert desktop.main(["--demo"]) == 0
    root = tk.roots[0]
    assert (root.quits, root.destroyed) == (1, 1)


def test_fr018_close_box_exits_0(tk):
    tk.driver = lambda root: root.call(root.protocols["WM_DELETE_WINDOW"])
    assert desktop.main(["--demo"]) == 0
    assert tk.roots[0].destroyed == 1


def test_fr018_worker_thread_ends_when_the_window_closes(tk):
    workers = []

    def driver(root):
        run_until(root, lambda: root.titles[-1].startswith("IN RANGE"), "the demo reading")
        workers.extend(t for t in threading.enumerate() if t.name == "lightkeeper-fetch")
        root.press("q")

    tk.driver = driver
    assert desktop.main(["--demo"]) == 0
    assert workers and all(worker.daemon for worker in workers)
    deadline = time.monotonic() + WAIT_SECONDS
    while any(worker.is_alive() for worker in workers):
        assert time.monotonic() < deadline, "the worker thread is still running"
        time.sleep(0.005)


def test_fr018_ctrl_c_in_the_main_loop_exits_130(tk, capsys):
    def driver(root):
        raise KeyboardInterrupt

    tk.driver = driver
    assert desktop.main(["--demo"]) == 130
    assert capsys.readouterr().err == "lightkeeper: stopped\n"
    assert tk.roots[0].destroyed == 1


def test_fr018_ctrl_c_during_a_callback_exits_130(tk, capsys):
    """Tk hands an exception in a callback to report_callback_exception, Ctrl+C too."""

    def interrupted():
        raise KeyboardInterrupt

    tk.driver = lambda root: root.call(interrupted)
    assert desktop.main(["--demo"]) == 130
    assert capsys.readouterr().err == "lightkeeper: stopped\n"
    root = tk.roots[0]
    assert (root.quits, root.destroyed, root.reported) == (1, 1, [])


def test_fr018_unexpected_callback_error_closes_the_window_and_is_raised(tk):
    """A window that stopped updating must not stay on screen looking alive."""

    def broken():
        raise RuntimeError("a bug")

    def driver(root):
        root.call(broken)
        root.call(broken)  # a second one, before the loop stops, does not replace the first

    tk.driver = driver
    with pytest.raises(RuntimeError, match="a bug"):
        desktop.main(["--demo"])
    assert tk.roots[0].destroyed == 1


def test_fr018_window_closes_when_the_worker_cannot_start(tk, monkeypatch):
    def no_thread():
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(desktop, "Worker", no_thread)
    with pytest.raises(RuntimeError, match="can't start new thread"):
        desktop.main(["--demo"])
    assert tk.roots[0].destroyed == 1


# --- options ------------------------------------------------------------------------------


def test_fr018_options_reach_the_window(tk):
    tk.driver = lambda root: root.press("q")
    assert desktop.main(["--demo", "--scale", "3", "--panel", "trmnl", "--on-top"]) == 0
    root = tk.roots[0]
    assert root.attribute_calls == [("-topmost", True)]
    assert tk.photos[0].data.startswith(b"P6\n2400 1440\n255\n")
    assert tk.system_calls == ["theme", "pixels"]  # auto theme, and device pixels first


def test_fr018_theme_option_skips_the_system_theme(tk):
    tk.driver = lambda root: root.press("q")
    assert desktop.main(["--demo", "--theme", "dark"]) == 0
    assert tk.system_calls == ["pixels"]
    assert tk.canvases[1].options["background"] == DARK.paper
    assert tk.roots[0].attribute_calls == []
    assert desktop.main(["--demo", "--theme", "light"]) == 0
    assert tk.canvases[3].options["background"] == LIGHT.paper


def test_fr018_panel_larger_than_the_screen_is_shown_smaller_and_says_so(tk, capsys):
    tk.screen = (1920, 1080)
    tk.driver = lambda root: root.press("q")
    assert desktop.main(["--demo", "--panel", "kindle"]) == 0
    assert tk.photos[0].data.startswith(b"P6\n600 800\n255\n")
    assert capsys.readouterr().err == (
        "lightkeeper: at --scale 2 the kindle panel is larger than this screen, so each "
        "panel pixel is drawn as 1x1 screen pixels instead of 2x2\n"
    )


def test_fr018_panel_the_screen_cannot_hold_exits_2(tk, capsys):
    tk.screen = (1366, 768)
    assert desktop.main(["--demo", "--panel", "kindle"]) == 2
    assert capsys.readouterr().err == (
        "Configuration error: a 600x800 panel does not fit on this 1366x768 screen even at "
        "one screen pixel a panel pixel: choose a smaller panel\n"
    )
    [root] = tk.roots
    assert root.destroyed == 1 and tk.photos == []


def test_fr018_ticker_polls_when_tk_timers_stall(tk, monkeypatch):
    """No after() timer ever fires here; the ticker thread's wake-ups bring the answer in."""
    monkeypatch.setattr(desktop, "POLL_MS", 5)
    source = GatedSource(fresh_entries())
    source.gate.set()
    use_source(monkeypatch, source)
    tickers = []

    def driver(root):
        deadline = time.monotonic() + WAIT_SECONDS
        while not root.titles[-1].startswith("IN RANGE"):
            assert time.monotonic() < deadline, "timed out waiting for a wake-up"
            root.deliver()
            time.sleep(0.001)
        tickers.extend(t for t in threading.enumerate() if t.name == "lightkeeper-tick")
        root.press("q")

    tk.driver = driver
    assert desktop.main([]) == 0
    assert tk.roots[0].now_ms == 0  # the fake after() clock never moved
    assert tickers and all(ticker.daemon for ticker in tickers)
    deadline = time.monotonic() + WAIT_SECONDS
    while any(ticker.is_alive() for ticker in tickers):
        assert time.monotonic() < deadline, "the ticker thread is still running"
        time.sleep(0.005)


def test_fr018_ticker_wakes_every_period_until_stopped():
    calls = []
    enough = threading.Event()

    def wake():
        calls.append(threading.current_thread().name)
        if len(calls) == 1:
            raise RuntimeError("main thread is not in main loop")  # skips one beat only
        if len(calls) >= 3:
            enough.set()

    ticker = desktop.Ticker(wake, 0.001)
    try:
        assert enough.wait(WAIT_SECONDS)
    finally:
        ticker.stop()
    ticker._thread.join(WAIT_SECONDS)
    assert not ticker._thread.is_alive() and ticker._thread.daemon
    assert set(calls) == {"lightkeeper-tick"}


def child_ticker_alone_brings_the_demo_reading_in():
    """On real Tk, with the after() poll stalled after its first beat, the ticker polls.

    As a clock set back stalls Tk 8.6's after() timers: the fetch goes out at
    the first poll, and only the ticker thread's wake-ups bring its answer in.
    """
    tkinter = real_tkinter()
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as error:
        print(f"no display: {error}")
        sys.exit(NO_REAL_TK)
    polls = []
    poll = desktop.Session._poll

    def tick_once(session):
        poll(session)  # never set again: a stalled after() timer

    def counted(session):
        polls.append(threading.current_thread())
        poll(session)

    desktop.Session._tick = tick_once
    desktop.Session._poll = counted  # what the wake-up binding runs
    seen = {}
    mainloop = tk_window.GlanceWindow.mainloop

    def watched(window):
        started = time.monotonic()

        def look():
            seen["title"] = window.root.title()
            if seen["title"].startswith("IN RANGE") or time.monotonic() - started > 5:
                window.quit()
            else:
                window.after(50, look)

        window.after(50, look)
        mainloop(window)

    tk_window.GlanceWindow.mainloop = watched
    assert desktop.main(["--demo", "--theme", "light"]) == 0
    assert seen["title"].startswith("IN RANGE - 3 min ago - checked "), seen
    assert polls and set(polls) == {threading.main_thread()}  # on Tk's thread, every one
    print("ok")


def test_fr018_real_tk_ticker_alone_keeps_the_window_polling():
    run_real_tk("tests.test_desktop", "child_ticker_alone_brings_the_demo_reading_in")


# --- the session, with a fake window, worker and clock ------------------------------------


class FakeWindow:
    def __init__(self):
        self.shown = []
        self.timers = {}
        self.cancelled = []
        self.quits = 0
        self.on_wake = None
        self._jobs = 0

    def show(self, lines, title, drawn_at):
        self.shown.append((lines, title, drawn_at))

    def bind_wake(self, callback):
        self.on_wake = callback

    def wake(self):
        """Run the binding at once, as Tk's thread would for the ticker's wake-up."""
        self.on_wake()

    def after(self, delay_ms, callback):
        self._jobs += 1
        self.timers[self._jobs] = (delay_ms, callback)
        return self._jobs

    def after_cancel(self, job):
        self.cancelled.append(job)
        del self.timers[job]

    def quit(self):
        self.quits += 1

    def fire(self, callback):
        """Fire the newest pending timer whose callback is `callback`."""
        job = max(j for j, (_delay, cb) in self.timers.items() if cb == callback)
        _delay, cb = self.timers.pop(job)
        cb()


class FakeWorker:
    def __init__(self):
        self.submitted = []
        self.answers = []
        self.closed = False
        self.alive = True  # its thread: until the test ends it

    def submit(self, fetch):
        self.submitted.append(fetch)

    def finished(self):
        answers, self.answers = self.answers, []
        return answers

    def close(self):
        self.closed = True


class FakeTicker:
    def __init__(self, wake, period):
        self.wake = wake
        self.period = period
        self.stopped = False

    def stop(self):
        self.stopped = True


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class Started:
    """The session's workers and ticker, as its factories made them."""

    def __init__(self):
        self.workers = []
        self.tickers = []

    def new_worker(self):
        self.workers.append(FakeWorker())
        return self.workers[-1]

    def new_ticker(self, wake, period):
        self.tickers.append(FakeTicker(wake, period))
        return self.tickers[-1]

    def submitted(self):
        return [fetch for worker in self.workers for fetch in worker.submitted]


def session_at(now=NOW, window=None):
    clock = Clock(now)
    source = FakeSource(entries=[entry(mgdl=110, minutes_ago=14)])
    session = desktop.Session(Glance(Thresholds(), timedelta(seconds=60), now), source, clock)
    window, started = window or FakeWindow(), Started()
    session.start(window, started.new_worker, started.new_ticker)
    return session, window, started.workers[0], clock, source, started


def test_fr018_session_starts_on_no_data_and_submits_the_first_fetch():
    session, window, worker, clock, source, started = session_at()
    assert window.shown == [(tuple(NO_DATA), NO_DATA_TITLE, NOW)]
    assert worker.submitted == [source.fetch_entries]
    assert source.calls == 0  # submitted, never run here
    delays = sorted(delay for delay, _cb in window.timers.values())
    assert delays == [desktop.POLL_MS, 30_000]
    [ticker] = started.tickers
    assert (ticker.wake, ticker.period) == (window.wake, desktop.POLL_MS / 1000)
    assert window.on_wake == session._poll
    session.stop()
    assert ticker.stopped and worker.closed


def test_fr018_session_stop_before_start_is_fine():
    session = desktop.Session(Glance(Thresholds(), timedelta(seconds=60), NOW), FakeSource())
    session.stop()


def test_fr018_session_turns_stale_on_its_own_timer():
    session, window, worker, clock, source, started = session_at()
    worker.answers.append(source.entries)
    window.fire(session._tick)
    assert window.shown[-1][0][0] == "IN RANGE"
    assert window.cancelled  # the re-age timer restarted from the new screen
    # Only the re-age timer from here on: the reading turns STALE with no fetch.
    while window.shown[-1][0][0] == "IN RANGE":
        delay = next(d for d, cb in window.timers.values() if cb == session._timer)
        clock.now += timedelta(milliseconds=delay)
        window.fire(session._timer)
    assert window.shown[-1][0][0] == "STALE - DO NOT TRUST"
    assert clock.now == NOW + timedelta(minutes=1, milliseconds=1)
    assert len(worker.submitted) == 1


def test_fr018_session_redraws_at_once_on_a_wake_jump():
    session, window, worker, clock, source, started = session_at()
    worker.answers.append(source.entries)
    window.fire(session._tick)
    shown = len(window.shown)
    clock.now += timedelta(hours=2)
    window.fire(session._tick)
    assert len(window.shown) == shown + 1
    assert window.shown[-1][0][0] == "STALE - DO NOT TRUST"
    assert len(worker.submitted) == 2  # and a fetch went out at once


def test_fr018_session_quiet_poll_draws_nothing():
    session, window, worker, clock, source, started = session_at()
    clock.now += timedelta(milliseconds=250)
    window.fire(session._tick)
    assert len(window.shown) == 1 and len(worker.submitted) == 1


def test_fr018_session_hung_fetch_is_redrawn_as_unreachable():
    session, window, worker, clock, source, started = session_at()
    for step in (timedelta(seconds=60), timedelta(seconds=60)):
        clock.now += step
        window.fire(session._tick)
    assert len(window.shown) == 1  # two intervals with no answer: not yet given up
    clock.now += timedelta(milliseconds=1)
    window.fire(session._tick)
    lines, title, _at = window.shown[-1]
    assert lines == (*NO_DATA, "Nightscout unreachable")
    assert "checked" in title
    assert len(started.submitted()) == 1  # the next fetch waits an interval


def test_haz002_hung_fetch_is_retried_on_a_new_worker_one_interval_later():
    """A fetch that never returns holds its thread; the next one gets a new thread."""
    session, window, hung, clock, source, started = session_at()
    for step in (timedelta(seconds=60), timedelta(seconds=60), timedelta(milliseconds=1)):
        clock.now += step  # in steps no longer than two intervals: no jump
        window.fire(session._tick)
    assert window.shown[-1][0][-1] == "Nightscout unreachable"  # the watchdog gave up on it
    assert hung.closed  # its thread ends whenever the hung fetch returns
    [_hung, fresh] = started.workers
    assert fresh.submitted == []
    clock.now += timedelta(seconds=60) - timedelta(milliseconds=1)
    window.fire(session._tick)
    assert fresh.submitted == []  # not before the interval is up
    clock.now += timedelta(milliseconds=1)
    window.fire(session._tick)
    assert fresh.submitted == [source.fetch_entries]
    assert hung.submitted == [source.fetch_entries]  # nothing more for the hung one
    # The hung fetch's late answer is never read; the fresh one's is.
    hung.answers.append([entry(mgdl=250, minutes_ago=0)])
    fresh.answers.append([entry(mgdl=99, minutes_ago=0)])
    window.fire(session._tick)
    assert window.shown[-1][0][:2] == ("IN RANGE", "99 mg/dL ->")
    assert hung.answers  # still unread
    assert len(started.workers) == 2


def tick_until(session, window, clock, condition, what):
    """Move the fake clock 30 s a poll (never a jump) until `condition()`."""
    for _ in range(100):
        if condition():
            return
        clock.now += timedelta(seconds=30)
        window.fire(session._tick)
    raise AssertionError(f"never saw {what}")


def test_haz002_threads_stuck_on_hung_fetches_are_capped(monkeypatch):
    """A server that never answers cannot pile up threads; one that ends frees a place."""
    monkeypatch.setattr(desktop, "HUNG_LIMIT", 2)
    session, window, first, clock, source, started = session_at()
    tick_until(session, window, clock, lambda: len(started.workers) == 2, "the first give-up")
    second = started.workers[1]
    tick_until(session, window, clock, lambda: second.submitted, "the retry")
    tick_until(session, window, clock, lambda: len(started.workers) == 3, "the second give-up")
    third = started.workers[2]
    # Two threads are stuck: no fetch starts, however long it waits, and the screen ages.
    for _ in range(20):
        clock.now += timedelta(seconds=30)
        window.fire(session._tick)
    assert third.submitted == [] and len(started.workers) == 3
    lines = window.shown[-1][0]
    assert lines[0] == "NO DATA" and lines[-1] == "Nightscout unreachable"
    session.refresh()  # nor does `r`
    assert third.submitted == []
    # The first hung fetch returns at last: its thread ends, and the next poll fetches.
    first.alive = False
    clock.now += timedelta(milliseconds=250)
    window.fire(session._tick)
    assert third.submitted == [source.fetch_entries]
    third.answers.append([entry(mgdl=99, minutes_ago=(NOW - clock.now) / timedelta(minutes=1))])
    window.fire(session._tick)
    assert window.shown[-1][0][:2] == ("IN RANGE", "99 mg/dL ->")


def test_fr018_clock_set_back_is_seen_through_the_ticker_not_tk_timers():
    """Tk 8.6 times after() by the wall clock; the ticker's wake-up polls regardless."""
    tk = FakeTk()
    window = tk_window.GlanceWindow(tk, 296, 128, platform="linux")
    session, window, worker, clock, source, started = session_at(window=window)
    root = tk.roots[0]
    worker.answers.append(source.entries)
    root.deliver()  # nothing queued yet
    started.tickers[0].wake()  # as the ticker thread does, every POLL_MS
    root.deliver()
    assert root.titles[-1].startswith("IN RANGE - 14 min ago - checked")
    stalled = {job for _due, _seq, job, _cb in root.timers}
    # The clock goes back an hour. No after() timer fires: in Tk 8.6 they would wait an
    # hour. Only the ticker's wake-ups come.
    clock.now -= timedelta(hours=1)
    started.tickers[0].wake()
    root.deliver()
    # Re-classified at once: the reading is now 46 minutes ahead of the clock.
    assert root.titles[-1].startswith("STALE - DO NOT TRUST - time is in the future - checked")
    assert len(worker.submitted) == 2  # a fetch went out at once
    redraws = [job for _due, _seq, job, cb in root.timers if cb == session._timer]
    assert len(redraws) == 1 and redraws[0] not in stalled  # the re-age timer, set again


def test_fr018_session_refresh_and_fail():
    session, window, worker, clock, source, started = session_at()
    session.refresh()
    assert len(worker.submitted) == 1  # one is out already
    worker.answers.append([])
    window.fire(session._tick)
    session.refresh()
    assert len(worker.submitted) == 2
    first, second = RuntimeError("one"), RuntimeError("two")
    session.fail(first)
    session.fail(second)
    assert session.failure is first and window.quits == 2


def test_fr018_worker_answers_with_entries_or_the_error_without_its_traceback():
    worker = desktop.Worker()
    try:
        worker.submit(lambda: [1, 2])

        def broken():
            raise OSError("no route")

        worker.submit(broken)
        answers = []
        deadline = time.monotonic() + WAIT_SECONDS
        while len(answers) < 2:
            assert time.monotonic() < deadline
            answers += worker.finished()
            time.sleep(0.001)
    finally:
        worker.close()
    assert answers[0] == [1, 2]
    assert isinstance(answers[1], OSError) and answers[1].__traceback__ is None
    assert worker.finished() == []


def test_haz002_worker_is_alive_until_closed_and_done():
    release = threading.Event()
    worker = desktop.Worker()
    worker.submit(lambda: [] if release.wait(WAIT_SECONDS) else ["timed out"])
    worker.close()
    assert worker.alive  # still running the fetch it had when closed
    release.set()
    worker._thread.join(WAIT_SECONDS)
    assert not worker.alive
    assert worker.finished() == [[]]


# --- tkinter stays out of the CLI and the Pi ----------------------------------------------


def run_python(code):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    result = subprocess.run(  # noqa: S603 - fixed arguments, this interpreter
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_fr018_cli_never_loads_tkinter():
    code = (
        "import sys\n"
        "from lightkeeper import cli\n"
        "cli.main(['--demo'])\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('tkinter', '_tkinter')))\n"
    )
    assert run_python(code).splitlines()[-1] == "[]"


def test_fr018_desktop_loads_tkinter_only_when_the_window_opens():
    code = (
        "import sys\n"
        "import lightkeeper.desktop, lightkeeper.infrastructure.tk_window\n"
        "import lightkeeper.application.glance, lightkeeper.infrastructure.ppm\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('tkinter', '_tkinter')))\n"
    )
    assert run_python(code) == "[]"

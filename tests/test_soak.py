"""GAP-004: an accelerated multi-day --watch soak.

Three days of 60-second cycles (4,320) run through the real `cli.main` loop
in a few seconds: a fake clock advances on every sleep, a fake source serves
a fresh reading (or fails during an outage), and the SVG is written every
cycle. Checks that memory does not grow, that every cycle reads the clock
afresh (no drift from accumulated sleeps), that an outage ages into STALE and
recovers, and that a backwards clock jump during the outage shows STALE.
"""

import io
import os
import tracemalloc
from datetime import UTC, datetime, timedelta

from lightkeeper import cli
from lightkeeper.domain.status import Level

START = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
INTERVAL = 60
DAYS = 3
CYCLES = DAYS * 24 * 60 * 60 // INTERVAL
MIDPOINT = (300 + CYCLES) // 2
OUTAGE = range(1000, 1040)  # 40 cycles with Nightscout down
# Mid-outage, the wall clock steps back 20 minutes (an NTP correction), so the
# last good reading the display is aging suddenly looks future-dated.
CLOCK_JUMP_AT = OUTAGE.start + 5
CLOCK_JUMP_SECONDS = -20 * 60


class Clock:
    def __init__(self):
        self.now = START

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class FakeDatetime:
    """Stands in for `datetime` inside cli: only `now` is used there."""

    clock = None

    @classmethod
    def now(cls, tz=None):
        return cls.clock.now


class Source:
    """Fresh reading two minutes old on every fetch, except during the outage."""

    def __init__(self, clock, cycle):
        self.clock = clock
        self.cycle = cycle

    def fetch_entries(self, count=12):
        if self.cycle[0] in OUTAGE:
            raise OSError("connection refused")
        ms = int((self.clock.now - timedelta(minutes=2)).timestamp() * 1000)
        return [{"type": "sgv", "sgv": 112, "date": ms, "direction": "Flat"}]


class NullOut(io.TextIOBase):
    def write(self, text):
        return len(text)


def test_gap004_three_day_watch_soak(monkeypatch, tmp_path):
    clock = Clock()
    cycle = [0]
    levels = []
    memory = {}

    FakeDatetime.clock = clock
    monkeypatch.setattr(cli, "datetime", FakeDatetime)
    monkeypatch.setattr(cli, "NightscoutClient", lambda url, token=None: Source(clock, cycle))
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")
    monkeypatch.setattr(cli.sys, "stdout", NullOut())
    monkeypatch.setattr(cli.sys, "stderr", NullOut())

    real_current_status = cli.current_status

    def recording_current_status(*args, **kwargs):
        status, error = real_current_status(*args, **kwargs)
        levels.append((cycle[0], status.level, status.age_minutes))
        return status, error

    monkeypatch.setattr(cli, "current_status", recording_current_status)

    def fake_sleep(seconds):
        assert seconds == INTERVAL
        cycle[0] += 1
        if cycle[0] == 300:
            tracemalloc.start()
            memory["start"] = tracemalloc.take_snapshot()
        if cycle[0] == MIDPOINT:
            memory["mid"] = tracemalloc.take_snapshot()
        if cycle[0] == CYCLES:
            memory["end"] = tracemalloc.take_snapshot()
            tracemalloc.stop()
            raise KeyboardInterrupt
        # A little scheduling jitter every cycle; it must not accumulate into
        # the displayed age, because every cycle reads the clock afresh.
        clock.advance(seconds + 0.25)
        if cycle[0] == CLOCK_JUMP_AT:
            clock.advance(CLOCK_JUMP_SECONDS)

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)

    svg = tmp_path / "screen.svg"
    assert cli.main(["--watch", "--interval", str(INTERVAL), "--svg", str(svg)]) == 0
    assert len(levels) == CYCLES
    assert svg.read_text(encoding="utf-8").startswith("<svg")

    # Memory: compare two equal windows of about 2,000 cycles each. Caches in
    # the standard library may still be filling during the first window (by
    # how much depends on the platform), but a leak keeps growing in the
    # second. Only allocations made by src/lightkeeper are counted, because
    # the test's own recording list grows by design.
    #
    # The limit sits between noise and a leak, closer to the leak than it
    # should. CPython 3.14 leaves some short-lived blocks (strftime and
    # isoformat results among them) allocated after they are dropped, still
    # attributed to the line that made them; a plain loop of `strftime` with no
    # Lightkeeper code shows it, and in this suite it reached about 11 KB in the
    # second window, depending on what ran before. The smallest leak there is,
    # one more pointer a cycle (a list keeping a reference to a shared object),
    # measured about 16.7 KB in the second window: just above the limit, so it
    # is caught, but with about 2% to spare. A leaked new object a cycle adds
    # its own size on top (at least 2,000 x 36 bytes = 72 KB). Separating noise
    # from a leak by more (growth across three windows, say) is follow-up work.
    def ours(later, earlier):
        stats = later.compare_to(earlier, "filename")
        mine = [s for s in stats if os.path.join("src", "lightkeeper") in s.traceback[0].filename]
        return sum(s.size_diff for s in mine), mine[:5]

    first, _ = ours(memory["mid"], memory["start"])
    second, top = ours(memory["end"], memory["mid"])
    assert second < 16 * 1024, f"still growing in the second window ({first=}): {top}"

    by_cycle = {c: (level, age) for c, level, age in levels}
    # Fresh readings show their true age on day 3: no drift from jitter.
    assert by_cycle[CYCLES - 1] == (Level.IN_RANGE, 2)
    # The outage ages the last good reading into STALE, then recovers.
    assert by_cycle[OUTAGE.start][0] is Level.IN_RANGE
    assert by_cycle[OUTAGE.stop - 1][0] is Level.STALE
    assert by_cycle[OUTAGE.stop][0] is Level.IN_RANGE
    # The clock step makes the aging reading future-dated: STALE, never fresh.
    level, age = by_cycle[CLOCK_JUMP_AT]
    assert level is Level.STALE and age < 0
    # A last good reading always exists, so NO DATA never appears.
    assert all(level is not Level.NO_DATA for _, level, _ in levels)

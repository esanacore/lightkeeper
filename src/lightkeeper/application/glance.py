"""What the desktop glance window shows, and when it must change on its own (FR-018).

A window stays open for hours, so it cannot wait for the next fetch to notice
that its reading went old. This module keeps the window's state and answers
three questions for it, all from a clock it is handed, so every rule here is
tested with a fake clock:

- What to show now: the vector lines from `render_lines`, re-aged from the last
  good reading with no fetch, and a window title made verbatim from those lines
  (`window_title`).
- When to look again: at the next instant the lines can change (the age's next
  whole minute, the first stale millisecond, a future-dated reading coming into
  range, or the clock's next minute for the window's stamp), and never more
  than 30 seconds away, so STALE appears on time (HAZ-001, HAZ-008). Going
  STALE is one redraw: a change due in the second before it waits for it, so
  `15 min ago` never flashes up a millisecond before STALE replaces it.
- Whether something went wrong between looks: a wall-clock jump of more than two
  fetch intervals (sleep and wake, or a clock set by hand) re-classifies at once
  and asks for a fetch, and a fetch with no answer after two intervals counts as
  a fetch error, so a hung request turns into "Nightscout unreachable" and then
  STALE instead of a frozen window (HAZ-002).

The lines themselves are never decided here: `current_status` and
`render_lines` (application/monitor.py, pinned by spec/display_vectors.json)
are the only source, so STALE is still decided before any range check.

Imports only the domain layer and monitor.py, beside it; no clock, no thread,
no Tk.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from lightkeeper.application.monitor import current_status, render_lines
from lightkeeper.domain.glucose import GlucoseReading
from lightkeeper.domain.status import MAX_FUTURE_SKEW, Level, Status, Thresholds, classify

# The longest the window goes without re-aging its lines.
REAGE_PERIOD = timedelta(seconds=30)
# A look due this little before the first stale instant waits for it instead.
SETTLE = timedelta(seconds=1)
# A wall-clock step this many fetch intervals long is a jump: sleep, or a clock change.
JUMP_INTERVALS = 2
# A fetch with no answer this many fetch intervals after it started is a fetch error.
WATCHDOG_INTERVALS = 2

TITLE_SEPARATOR = " - "
TITLE_NAME = "Lightkeeper"
# Static loading copy (docs/BRAND.md, Motion and sound), until the first answer.
CHECKING = "checking Nightscout..."
# render_lines' headline for a STALE screen; its age line is under the last: line.
STALE_HEADLINE = "STALE - DO NOT TRUST"

# Headlines with the age as their third line. NO DATA, and any headline not
# here, has no age line: its partner is the guidance line under it.
_AGED_HEADLINES = frozenset(
    [level.value for level in Level if level not in (Level.NO_DATA, Level.STALE)]
    + [STALE_HEADLINE]
)

_MINUTE = timedelta(minutes=1)
_MILLISECOND = timedelta(milliseconds=1)
# The clock's resolution: the first instant past a limit (age > stale_after).
_TICK = timedelta(microseconds=1)


@dataclass(frozen=True)
class GlanceView:
    """One screen of the window: the vector lines and the window title."""

    lines: tuple[str, ...]
    title: str


def window_title(lines: Sequence[str], checked_at: datetime | None) -> str:
    """Return the title: `<headline> - <age or guidance> - checked HH:MM - Lightkeeper`.

    Every part but the clock comes verbatim from the lines, so a screen reader
    reading the title hears the real screen. The second part is the age line
    (`3 min ago`, `time is in the future`), or for NO DATA and any other
    headline its guidance line. `checked_at` is when Nightscout last answered
    (or was given up on), in local 24-hour time; before the first answer the
    title says `checking Nightscout...` instead, because nothing was checked.
    """
    headline = lines[0]
    partner = 2 if headline in _AGED_HEADLINES else 1
    parts = [headline, *lines[partner : partner + 1]]
    if checked_at is None:
        parts.append(CHECKING)
    else:
        parts.append(f"checked {checked_at.astimezone().strftime('%H:%M')}")
    parts.append(TITLE_NAME)
    return TITLE_SEPARATOR.join(parts)


class _Answer:
    """A finished fetch, handed to current_status as if it were the source.

    So an answer from the worker thread goes through exactly the code a fetch
    in the CLI goes through: parsed, classified, and any failure degraded.
    """

    def __init__(self, outcome: list[Any] | Exception) -> None:
        self._outcome = outcome

    def fetch_entries(self, count: int = 12) -> list[Any]:
        """Return the entries the fetch got, or raise the error it ended with."""
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class Glance:
    """The window's state: the last good reading, the fetch in flight, and the clock seen.

    The window starts on the NO DATA vector lines until the first answer.
    Every method takes `now`, a timezone-aware time, and none of them waits.
    """

    def __init__(self, thresholds: Thresholds, interval: timedelta, now: datetime) -> None:
        """Start with no reading, and a fetch due at once; `interval` is between fetches."""
        if interval <= timedelta(0):
            raise ValueError("interval must be positive")
        self._thresholds = thresholds
        self._interval = interval
        self._last_good: Status | None = None
        self._error: str | None = None
        self._checked_at: datetime | None = None
        self._fetch_started: datetime | None = None
        self._gave_up = False  # the watchdog already counted the fetch in flight as failed
        self._next_fetch = now
        self._seen = now  # the clock at the last poll, to see a jump

    @property
    def checked_at(self) -> datetime | None:
        """When Nightscout last answered or was given up on; None before the first answer."""
        return self._checked_at

    @property
    def fetching(self) -> bool:
        """True while a fetch is in flight, given up on or not."""
        return self._fetch_started is not None

    def _reading(self) -> GlucoseReading | None:
        return self._last_good.reading if self._last_good is not None else None

    def view(self, now: datetime) -> GlanceView:
        """Return the screen at `now`: the last good reading re-aged, with no fetch."""
        status = classify(self._reading(), now, self._thresholds)
        lines = render_lines(status, self._error)
        return GlanceView(tuple(lines), window_title(lines, self._checked_at))

    def next_redraw_ms(self, now: datetime) -> int:
        """Return how many milliseconds from `now` to look again, from 1 to 30,000.

        Whole milliseconds, as Tk's after() counts them, rounded up, so a look is
        never early: a reading that turns STALE one millisecond past the limit is
        looked at on that millisecond.

        No look is set for the second before STALE. The age line's last fresh
        minute (`15 min ago`) falls a microsecond before it, and drawing it
        would put a fresh screen up for a moment before STALE replaced it: two
        redraws for one change. Such a look waits for STALE when STALE is within
        30 seconds, and otherwise comes a second earlier.
        """
        target = min(self._next_change(now), now + REAGE_PERIOD)
        reading = self._reading()
        if reading is not None:
            stale_at = self._stale_at(reading)
            if stale_at - SETTLE < target < stale_at:
                target = stale_at if stale_at - now <= REAGE_PERIOD else stale_at - SETTLE
        return max(1, -(-(target - now) // _MILLISECOND))

    def _stale_at(self, reading: GlucoseReading) -> datetime:
        """Return the first instant classify() says STALE: age > stale_after."""
        return reading.timestamp + self._thresholds.stale_after + _TICK

    def _next_change(self, now: datetime) -> datetime:
        """Return the next instant after `now` at which the screen can change."""
        # The window stamps its bitmap with the clock's HH:MM, so a new minute is a change.
        candidates = [now.replace(second=0, microsecond=0) + _MINUTE]
        reading = self._reading()
        if reading is not None:
            stamp = reading.timestamp
            age_minutes = (now - stamp) // _MINUTE
            candidates += [
                # The age line's next whole minute ("just now" until the first).
                stamp + max(1, age_minutes + 1) * _MINUTE,
                self._stale_at(reading),
                # A future-dated reading comes into range at a skew of 2 minutes.
                stamp - MAX_FUTURE_SKEW,
            ]
        return min(moment for moment in candidates if moment > now)

    def poll(self, now: datetime) -> bool:
        """Look for a wall-clock jump and a hung fetch; True means re-classify at once.

        Called every few hundred milliseconds. A step of more than two fetch
        intervals since the last poll is sleep and wake, or a clock change: the
        screen is re-classified now, not at the next timer, and a fetch is due.
        A fetch with no answer two intervals after it started is counted, once,
        as a fetch error, so the screen says "Nightscout unreachable" and goes on
        aging into STALE (HAZ-002). Its answer, if one ever comes, is still used.
        """
        limit = JUMP_INTERVALS * self._interval
        jumped = abs(now - self._seen) > limit
        self._seen = now
        if jumped:
            self._next_fetch = now
            if self._fetch_started is not None and self._fetch_started > now:
                # The clock went back: count the watchdog's wait from now.
                self._fetch_started = now
        overdue = (
            self._fetch_started is not None
            and not self._gave_up
            and now - self._fetch_started > WATCHDOG_INTERVALS * self._interval
        )
        if overdue:
            self._gave_up = True
            self._error = (
                f"no answer from Nightscout within "
                f"{int((WATCHDOG_INTERVALS * self._interval).total_seconds())} seconds"
            )
            self._checked_at = now
        return jumped or overdue

    def fetch_due(self, now: datetime) -> bool:
        """Say whether a fetch should start: none is in flight and its time has come."""
        return self._fetch_started is None and now >= self._next_fetch

    def refresh(self, now: datetime) -> None:
        """Ask for a fetch at once (the `r` key); ignored while one is in flight."""
        if self._fetch_started is None:
            self._next_fetch = now

    def fetch_started(self, now: datetime) -> None:
        """Note that a fetch started at `now`; the next is due one interval later."""
        self._fetch_started = now
        self._gave_up = False
        self._next_fetch = now + self._interval

    def fetch_finished(self, outcome: list[Any] | Exception, now: datetime) -> None:
        """Take a fetch's answer: the raw entries, or the error it ended with.

        Exactly what the CLI does with a fetch: the newest valid reading
        becomes the last good one, and on an error the last good reading is
        kept and re-aged, with "Nightscout unreachable" under it.
        """
        status, error = current_status(_Answer(outcome), now, self._thresholds, self._last_good)
        if error is None:
            self._last_good = status
        self._error = error
        self._checked_at = now
        self._fetch_started = None
        self._gave_up = False

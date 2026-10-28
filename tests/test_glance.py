"""FR-018, HAZ-001, HAZ-002, HAZ-008: the desktop glance ages on its own clock.

Every test here hands the glance a fake clock (plain datetimes). The window
re-ages its last good reading with no fetch, so it goes STALE at the first
stale millisecond; a wall-clock jump (sleep and wake) re-classifies at once;
and a fetch that never answers turns into "Nightscout unreachable", then
STALE, instead of a frozen window. Every line still comes from current_status
and render_lines, so the vectors hold here too.
"""

import re
from datetime import UTC, datetime, timedelta

import pytest

from lightkeeper.application import glance as glance_module
from lightkeeper.application.glance import (
    CHECKING,
    REAGE_PERIOD,
    STALE_HEADLINE,
    Glance,
    GlanceView,
    window_title,
)
from lightkeeper.application.monitor import render_lines
from lightkeeper.domain.glucose import parse_entries
from lightkeeper.domain.status import Thresholds, classify
from tests.helpers import NOW, entry
from tests.test_vectors import VECTORS, raw_entries, thresholds

INTERVAL = timedelta(seconds=60)
MINUTE = timedelta(minutes=1)
SECOND = timedelta(seconds=1)
MS = timedelta(milliseconds=1)
NO_DATA = ("NO DATA", "Check sensor and phone", "Confirm on primary device")
UNREACHABLE = "Nightscout unreachable"


def clock(moment):
    """Return the title's clock for `moment`: local 24-hour HH:MM."""
    return moment.astimezone().strftime("%H:%M")


def answered(entries, at=NOW, interval=INTERVAL, limits=None):
    """Return a glance that asked Nightscout at `at` and got `entries` (or an exception)."""
    glance = Glance(limits or Thresholds(), interval, at)
    glance.fetch_started(at)
    glance.fetch_finished(entries, at)
    return glance


def walk(glance, start, until):
    """Follow the re-age timer from `start`: every instant the window looks, up to `until`."""
    moments, now = [], start
    while now <= until:
        moments.append(now)
        delay = glance.next_redraw_ms(now)
        assert 1 <= delay <= 30_000
        now += delay * MS
    return moments


# --- the first screen and the title -------------------------------------------------------


def test_fr018_window_starts_on_the_no_data_vector_lines():
    glance = Glance(Thresholds(), INTERVAL, NOW)
    view = glance.view(NOW)
    assert view == GlanceView(
        NO_DATA, "NO DATA - Check sensor and phone - checking Nightscout... - Lightkeeper"
    )
    assert glance.checked_at is None
    assert glance.fetch_due(NOW) and not glance.fetching


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr018_titles_for_every_display_vector(case):
    """The glance shows each vector's exact lines, and the title is made verbatim from them."""
    glance = answered(raw_entries(case), limits=thresholds(case))
    if case["error"]:
        glance.fetch_started(NOW)
        glance.fetch_finished(RuntimeError(case["error"]), NOW)
    view = glance.view(NOW)
    lines = case["lines"]
    assert view.lines == tuple(lines)
    partner = lines[1] if case["level"] == "NO DATA" else lines[2]
    if case["level"] != "NO DATA":
        assert re.fullmatch(r"just now|\d+ min ago|time is in the future", partner)
    assert view.title == f"{lines[0]} - {partner} - checked {clock(NOW)} - Lightkeeper"


@pytest.mark.parametrize(
    "lines,expected",
    [
        (["IN RANGE", "112 mg/dL ->", "3 min ago"], "IN RANGE - 3 min ago"),
        (["URGENT LOW", "LOW (<40)", "just now", UNREACHABLE], "URGENT LOW - just now"),
        (
            [STALE_HEADLINE, "last: 120 mg/dL ->", "time is in the future", UNREACHABLE],
            "STALE - DO NOT TRUST - time is in the future",
        ),
        ([*NO_DATA, UNREACHABLE], "NO DATA - Check sensor and phone"),
        # Any other headline gets the most cautious reading: no age line is assumed.
        (["SOMETHING NEW", "a line", "another"], "SOMETHING NEW - a line"),
        (["ALONE"], "ALONE"),
    ],
)
def test_fr018_title_partner_is_the_age_line_or_the_guidance(lines, expected):
    checked = datetime(2026, 10, 18, 23, 7).astimezone()
    assert window_title(lines, checked) == f"{expected} - checked 23:07 - Lightkeeper"


def test_fr018_title_says_checking_until_nightscout_first_answers():
    assert window_title(list(NO_DATA), None) == (
        f"NO DATA - Check sensor and phone - {CHECKING} - Lightkeeper"
    )


def test_fr018_title_clock_is_local_24_hour_time():
    late = datetime(2026, 10, 18, 21, 45, 59).astimezone()  # 9:45 pm, wherever this runs
    assert window_title(["IN RANGE", "1", "just now"], late).endswith(
        " - checked 21:45 - Lightkeeper"
    )


def test_fr018_stale_headline_is_the_one_render_lines_writes():
    stale = classify(parse_entries([entry(minutes_ago=40)])[0], NOW, Thresholds())
    assert render_lines(stale)[0] == STALE_HEADLINE


# --- re-aging with no fetch ---------------------------------------------------------------


def test_fr018_reading_turns_stale_without_a_fetch():
    """A 14-minute reading shows STALE at the first stale millisecond, with no fetch."""
    glance = answered([entry(mgdl=120, minutes_ago=14)])
    stamp = NOW - 14 * MINUTE
    first_stale = stamp + Thresholds().stale_after + MS
    moments = walk(glance, NOW, first_stale)
    assert moments[-1] == first_stale
    assert glance.view(first_stale - MS).lines == ("IN RANGE", "120 mg/dL ->", "15 min ago")
    assert glance.view(first_stale).lines == (
        STALE_HEADLINE,
        "last: 120 mg/dL ->",
        "15 min ago",
        "Confirm on primary device",
    )
    # Every look before it showed the same fresh screen, so going STALE was one
    # redraw (15 min ago never flashed up first); and none of them needed a fetch.
    assert {glance.view(m).lines for m in moments[:-1]} == {
        ("IN RANGE", "120 mg/dL ->", "14 min ago")
    }
    assert moments == [NOW, NOW + 30 * SECOND, NOW + 59 * SECOND + MS, first_stale]
    assert not glance.fetching
    assert glance.checked_at == NOW


def reading_at(moment, mgdl=120):
    """Return a Nightscout entry dated exactly `moment`."""
    return entry(mgdl=mgdl) | {"date": int(moment.timestamp() * 1000)}


def test_fr018_going_stale_is_one_redraw():
    """No look lands in the second before STALE: such a look waits for STALE instead."""
    # STALE at NOW + 30.5 s: the 30 s cap would land in the second before it, so the
    # look comes a second early, then on the first stale millisecond.
    first_stale = NOW + 30 * SECOND + 500 * MS + MS
    glance = answered([reading_at(first_stale - MS - Thresholds().stale_after)])
    assert glance.next_redraw_ms(NOW) == 29_501
    assert glance.next_redraw_ms(NOW + 29_501 * MS) == 1_000
    assert walk(glance, NOW, first_stale)[-1] == first_stale
    # A look inside that second goes straight to STALE.
    assert glance.next_redraw_ms(first_stale - 300 * MS) == 300


def test_fr018_stamp_minute_just_before_stale_waits_for_stale():
    """The clock's new minute 0.5 s before STALE is drawn with STALE, in one redraw."""
    first_stale = NOW + 60 * SECOND + 500 * MS + MS
    glance = answered([reading_at(first_stale - MS - Thresholds().stale_after)])
    assert glance.next_redraw_ms(NOW + 40 * SECOND) == 20_501
    # 1.5 s before STALE, the clock's new minute is looked at on time.
    first_stale += SECOND
    glance = answered([reading_at(first_stale - MS - Thresholds().stale_after)])
    assert glance.next_redraw_ms(NOW + 40 * SECOND) == 20_000


def test_fr018_age_line_changes_on_the_minute_without_a_fetch():
    glance = answered([entry(minutes_ago=3)])
    stamp = NOW - 3 * MINUTE
    moments = walk(glance, NOW + 20 * timedelta(seconds=1), stamp + 4 * MINUTE)
    assert moments[-1] == stamp + 4 * MINUTE
    assert glance.view(moments[-1] - MS).lines[2] == "3 min ago"
    assert glance.view(moments[-1]).lines[2] == "4 min ago"


def test_fr018_stale_keeps_aging_minute_by_minute():
    glance = answered([entry(minutes_ago=40)])
    stamp = NOW - 40 * MINUTE
    moments = walk(glance, NOW, stamp + 42 * MINUTE)
    assert {stamp + 41 * MINUTE, stamp + 42 * MINUTE} <= set(moments)
    assert glance.view(stamp + 42 * MINUTE).lines[2] == "42 min ago"


def test_fr018_reage_never_waits_more_than_30_seconds():
    """Even with nothing to age (NO DATA), the window looks again within 30 s."""
    glance = Glance(Thresholds(), INTERVAL, NOW)
    assert glance.next_redraw_ms(NOW) == 30_000  # NOW is on the minute
    assert glance.next_redraw_ms(NOW + timedelta(seconds=45)) == 15_000
    assert REAGE_PERIOD == timedelta(seconds=30)


def test_fr018_next_look_is_whole_milliseconds_rounded_up():
    """A look is never early: a boundary 0.4 ms away is looked at in 1 ms."""
    glance = answered([entry(minutes_ago=0)])
    almost = NOW + MINUTE - timedelta(microseconds=400)
    assert glance.next_redraw_ms(almost) == 1
    assert glance.next_redraw_ms(NOW + MINUTE - timedelta(microseconds=1_400)) == 2


def test_fr018_next_look_includes_the_clock_minute_for_the_stamp():
    """The window's stamp is the clock's HH:MM, so a new minute is looked at on time."""
    glance = answered([entry(minutes_ago=0)], at=NOW - timedelta(seconds=10))
    # The reading's next minute is a minute after NOW; the clock's next minute is NOW.
    assert glance.next_redraw_ms(NOW - timedelta(seconds=10)) == 10_000


def test_fr018_future_reading_comes_into_range_on_time():
    """A reading 5 minutes ahead is STALE until its skew is 2 minutes, then fresh at once."""
    glance = answered([entry(mgdl=120, minutes_ago=-5)])
    stamp = NOW + 5 * MINUTE
    in_range = stamp - 2 * MINUTE
    moments = walk(glance, NOW, in_range)
    assert moments[-1] == in_range
    assert glance.view(in_range - MS).lines[2] == "time is in the future"
    assert glance.view(in_range).lines == ("IN RANGE", "120 mg/dL ->", "just now")
    # Then "just now" until the reading is a whole minute old.
    assert glance.next_redraw_ms(in_range) == 30_000
    assert walk(glance, in_range, stamp + MINUTE)[-1] == stamp + MINUTE


# --- wall-clock jumps ---------------------------------------------------------------------


def test_fr018_wake_jump_reclassifies_at_once():
    """Hours of sleep: the next poll re-classifies (STALE) and asks for a fetch at once."""
    glance = answered([entry(minutes_ago=2)])
    assert glance.poll(NOW + timedelta(seconds=1)) is False
    glance.fetch_started(NOW + timedelta(seconds=1))
    glance.fetch_finished([entry(minutes_ago=1)], NOW + timedelta(seconds=2))
    awake = NOW + timedelta(hours=3)
    assert glance.fetch_due(awake) is True  # overdue anyway; the jump makes it now
    assert glance.poll(awake) is True
    assert glance.view(awake).lines[0] == STALE_HEADLINE
    assert glance.fetch_due(awake)
    assert glance.poll(awake + timedelta(milliseconds=250)) is False


def test_fr018_clock_jump_makes_a_fetch_due_even_before_its_time():
    glance = answered([entry(minutes_ago=2)])
    glance.poll(NOW)
    # The clock steps back a day: the scheduled fetch is "a day away", but the jump overrides it.
    back = NOW - timedelta(days=1)
    assert glance.fetch_due(back) is False
    assert glance.poll(back) is True
    assert glance.fetch_due(back) is True


def test_fr018_a_step_of_two_intervals_is_not_a_jump():
    glance = answered([entry(minutes_ago=2)])
    assert glance.poll(NOW + 2 * INTERVAL) is False
    assert glance.poll(NOW + 4 * INTERVAL + MS) is True
    assert glance.poll(NOW + 2 * INTERVAL + MS) is False  # back by exactly two intervals


def test_fr018_clock_set_back_restarts_the_watchdog_count():
    glance = answered([entry(minutes_ago=2)])
    glance.fetch_started(NOW)
    back = NOW - timedelta(hours=1)
    assert glance.poll(back) is True
    assert glance.poll(back + 2 * INTERVAL) is False  # counted from the jump, not from NOW
    assert glance.poll(back + 2 * INTERVAL + MS) is True
    assert UNREACHABLE in glance.view(back + 2 * INTERVAL + MS).lines


def test_fr018_wake_with_a_fetch_in_flight_gives_up_on_it_at_once():
    glance = answered([entry(minutes_ago=2)])
    glance.fetch_started(NOW)
    awake = NOW + timedelta(hours=8)
    assert glance.poll(awake) is True
    view = glance.view(awake)
    assert view.lines[0] == STALE_HEADLINE and view.lines[-1] == UNREACHABLE
    assert glance.checked_at == awake


# --- the fetch watchdog -------------------------------------------------------------------


def test_fr018_hung_fetch_becomes_unreachable_then_stale():
    """A fetch that never answers: unreachable after two intervals, STALE on schedule."""
    glance = answered([entry(mgdl=110, minutes_ago=5)])
    stamp = NOW - 5 * MINUTE
    started = NOW + INTERVAL
    assert glance.fetch_due(started)
    glance.fetch_started(started)
    deadline = started + 2 * INTERVAL
    for now in (started + MS, deadline - MS, deadline):
        assert glance.poll(now) is False
    assert glance.view(deadline).lines == ("IN RANGE", "110 mg/dL ->", "8 min ago")

    assert glance.poll(deadline + MS) is True
    assert glance.view(deadline + MS).lines == (
        "IN RANGE",
        "110 mg/dL ->",
        "8 min ago",
        UNREACHABLE,
    )
    assert glance.checked_at == deadline + MS
    assert glance.view(deadline + MS).title == (
        f"IN RANGE - 8 min ago - checked {clock(deadline + MS)} - Lightkeeper"
    )
    # Still no answer: the re-age timer alone turns it STALE at the first stale millisecond.
    first_stale = stamp + Thresholds().stale_after + MS
    moments = walk(glance, deadline + MS, first_stale)
    assert moments[-1] == first_stale
    assert glance.view(first_stale).lines == (
        STALE_HEADLINE,
        "last: 110 mg/dL ->",
        "15 min ago",
        UNREACHABLE,
    )
    # No second fetch was started while the first is still in flight.
    assert glance.fetching and not glance.fetch_due(first_stale)


def test_fr018_watchdog_counts_a_hung_fetch_once():
    glance = answered([entry(minutes_ago=1)])
    glance.fetch_started(NOW)
    late = NOW + 2 * INTERVAL + MS
    assert glance.poll(late) is True
    assert glance.poll(late + timedelta(seconds=1)) is False
    assert glance.checked_at == late


def test_fr018_watchdog_message_names_the_wait():
    glance = answered([entry(minutes_ago=1)])
    glance.fetch_started(NOW)
    glance.poll(NOW + 2 * INTERVAL + MS)
    assert glance._error == "no answer from Nightscout within 120 seconds"


def test_fr018_late_answer_after_the_watchdog_is_still_used():
    glance = answered([entry(minutes_ago=1)])
    glance.fetch_started(NOW)
    late = NOW + 2 * INTERVAL + MS
    glance.poll(late)
    glance.fetch_finished([entry(mgdl=99, minutes_ago=0)], late + MS)
    assert glance.view(late + MS).lines == ("IN RANGE", "99 mg/dL ->", "2 min ago")
    assert not glance.fetching
    assert glance.fetch_due(late + MS)  # it started more than an interval ago


# --- fetching -----------------------------------------------------------------------------


def test_fr018_one_fetch_at_a_time_one_interval_apart():
    glance = Glance(Thresholds(), INTERVAL, NOW)
    glance.fetch_started(NOW)
    assert glance.fetching and not glance.fetch_due(NOW + 5 * INTERVAL)
    glance.fetch_finished([entry()], NOW + timedelta(seconds=2))
    assert not glance.fetch_due(NOW + INTERVAL - MS)
    assert glance.fetch_due(NOW + INTERVAL)


def test_fr018_refresh_asks_for_a_fetch_at_once_unless_one_is_running():
    glance = answered([entry()])
    soon = NOW + timedelta(seconds=5)
    assert not glance.fetch_due(soon)
    glance.refresh(soon)
    assert glance.fetch_due(soon)
    glance.fetch_started(soon)
    glance.refresh(soon + MS)
    glance.fetch_finished([entry()], soon + 2 * MS)
    assert not glance.fetch_due(soon + 2 * MS)  # the refresh while running was not kept


def test_fr018_failed_fetch_keeps_the_last_good_reading_aging():
    """Exactly what the CLI does: the last good reading, re-aged, under the warning."""
    glance = answered([entry(mgdl=101, minutes_ago=6)])
    later = NOW + MINUTE
    glance.fetch_started(later)
    glance.fetch_finished(OSError("no route"), later)
    assert glance.view(later).lines == ("IN RANGE", "101 mg/dL ->", "7 min ago", UNREACHABLE)
    glance.fetch_started(later + MINUTE)
    glance.fetch_finished([entry(mgdl=104, minutes_ago=-2)], later + MINUTE)
    assert glance.view(later + MINUTE).lines == ("IN RANGE", "104 mg/dL ->", "just now")


def test_fr018_answer_with_no_usable_reading_is_no_data():
    glance = answered([entry(minutes_ago=1)])
    glance.fetch_started(NOW)
    glance.fetch_finished([{"type": "mbg"}, "junk"], NOW)
    assert glance.view(NOW).lines == NO_DATA
    assert glance.next_redraw_ms(NOW) == 30_000


@pytest.mark.parametrize("interval", [timedelta(0), timedelta(seconds=-1)])
def test_fr018_interval_must_be_positive(interval):
    with pytest.raises(ValueError, match="interval must be positive"):
        Glance(Thresholds(), interval, NOW)


def test_fr018_glance_imports_no_clock_thread_or_tk():
    source = glance_module.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in (
        "import threading",
        "import time",
        "tkinter",
        "datetime.now",
        "infrastructure",
    ):
        assert forbidden not in text, forbidden


def test_fr018_glance_is_timezone_aware_only():
    glance = Glance(Thresholds(), INTERVAL, NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        glance.view(datetime(2026, 10, 18, 12, 0))
    assert glance.view(NOW.astimezone(UTC)).lines == NO_DATA

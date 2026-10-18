"""Glue between the Nightscout source and a display.

`current_status` fetches, parses, and classifies. `render_lines` turns a
Status into a few short plain-text lines that fit a small e-ink screen.
Connection failures become a STALE or NO DATA status instead of a crash,
because a display that silently freezes on its last value is a hazard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from glucose_watch.domain.glucose import parse_entries
from glucose_watch.domain.status import Level, Status, Thresholds, classify


class EntrySource(Protocol):
    """Anything that can hand back raw Nightscout entries."""

    def fetch_entries(self, count: int = 12) -> list: ...


def current_status(
    source: EntrySource,
    now: datetime,
    thresholds: Thresholds,
    last_good: Status | None = None,
) -> tuple[Status, str | None]:
    """Fetch the newest reading and classify it.

    Returns (status, error_message). On a fetch error, the last good reading
    (if any) is re-classified against `now`, so it ages into STALE on its
    own instead of being displayed forever.
    """
    try:
        readings = parse_entries(source.fetch_entries(count=12))
    except Exception as exc:  # any source failure must degrade, never crash
        previous = last_good.reading if last_good else None
        return classify(previous, now, thresholds), str(exc)

    newest = readings[0] if readings else None
    return classify(newest, now, thresholds), None


def render_lines(status: Status, error: str | None = None) -> list[str]:
    """Three to four short lines for a small display. Plain ASCII only."""
    if status.level is Level.NO_DATA or status.reading is None:
        lines = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
    else:
        reading = status.reading
        if reading.is_sensor_low_sentinel:
            value = "LOW (<40)"
        elif reading.is_sensor_high_sentinel:
            value = "HIGH (>400)"
        else:
            value = f"{reading.mgdl} mg/dL {reading.trend.arrow}"

        minutes = status.age_minutes
        age_text = "just now" if minutes == 0 else f"{minutes} min ago"
        if status.level is Level.STALE:
            if minutes is not None and minutes < 0:
                age_text = "time is in the future"
            lines = ["STALE - DO NOT TRUST", f"last: {value}", age_text, "Confirm on primary device"]
        else:
            lines = [status.level.value, value, age_text]

    if error:
        lines.append("Nightscout unreachable")
    return lines

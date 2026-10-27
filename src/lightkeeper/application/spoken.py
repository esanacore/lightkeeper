"""Say a Status in plain sentences, for screen readers (FR-017).

The spoken form is built from the Status itself, never by parsing the
rendered lines, and keeps the screen's order: the status, then the value,
then its age. It is never more current than the screen:

- the age is always spoken;
- STALE speaks its warning first and no trend word, because an arrow is a
  claim about now;
- NO DATA never speaks a number, and neither does anything this module
  cannot place, which gets the most cautious form.

spec/spoken_vectors.json pins one sentence per display vector, and the Swift
package (Spoken.swift) runs the same file. The text is meant for polite or
passive accessibility channels only. It is deliberately not published to Home
Assistant or to any text-to-speech path: Lightkeeper never sounds (HAZ-013).
"""

from __future__ import annotations

from lightkeeper.domain.glucose import GlucoseReading, Trend
from lightkeeper.domain.status import Level, Status

UNIT = "milligrams per deciliter"
STALE_WARNING = "Stale, do not trust."
FUTURE = "Reading time is in the future."
CONFIRM = "Confirm on the primary device."
UNREACHABLE = "Nightscout unreachable."
NO_DATA = ("No data.", "Check sensor and phone.", CONFIRM)

# Only the levels that may speak a current number. NO DATA and STALE have
# their own forms, and a level missing here is spoken as NO DATA.
_HEADLINES = {
    Level.URGENT_LOW: "Urgent low.",
    Level.LOW: "Low.",
    Level.IN_RANGE: "In range.",
    Level.HIGH: "High.",
    Level.URGENT_HIGH: "Urgent high.",
}

_TREND_NAMES = {
    Trend.DOUBLE_UP: "rising quickly",
    Trend.SINGLE_UP: "rising",
    Trend.FORTY_FIVE_UP: "rising slowly",
    Trend.FLAT: "steady",
    Trend.FORTY_FIVE_DOWN: "falling slowly",
    Trend.SINGLE_DOWN: "falling",
    Trend.DOUBLE_DOWN: "falling quickly",
    Trend.UNKNOWN: "trend unknown",
}


def spoken_name(trend: Trend) -> str:
    """Return the trend arrow in words, the way a screen reader should say it."""
    return _TREND_NAMES.get(trend, "trend unknown")


def spoken_age(minutes: int) -> str:
    """Say whole minutes as 'just now', '1 minute ago', or 'N minutes ago'."""
    if minutes == 0:
        return "just now"
    if minutes == 1:
        return "1 minute ago"
    return f"{minutes} minutes ago"


def spoken_text(status: Status, error: str | None = None) -> str:
    """Say what the screen shows, in a few short sentences in the screen's order.

    `error` is the fetch error passed to `render_lines`; when it is set,
    "Nightscout unreachable." is added at the end, as the screen adds its line.
    """
    sentences = _sentences(status)
    if error:
        sentences += (UNREACHABLE,)
    return " ".join(sentences)


def _sentences(status: Status) -> tuple[str, ...]:
    reading = status.reading
    minutes = status.age_minutes
    if status.level is Level.NO_DATA or reading is None or minutes is None:
        return NO_DATA

    # classify never pairs a fresh level with a negative age; if a Status
    # ever does, it is spoken as the future-dated STALE form, not as current.
    if status.level is Level.STALE or minutes < 0:
        if minutes < 0:
            return (STALE_WARNING, FUTURE, CONFIRM)
        last = f"Last reading {_value(reading)}, {spoken_age(minutes)}."
        return (STALE_WARNING, last, CONFIRM)

    headline = _HEADLINES.get(status.level)
    if headline is None:
        return NO_DATA

    if reading.is_sensor_low_sentinel or reading.is_sensor_high_sentinel:
        value = f"Sensor reads {_value(reading)}."
    else:
        value = f"{_value(reading)}, {spoken_name(reading.trend)}."
    age = spoken_age(minutes)
    return (headline, value, age[:1].upper() + age[1:] + ".")


def _value(reading: GlucoseReading) -> str:
    """Say the value without any trend: the number and its unit, or the sensor's limit."""
    if reading.is_sensor_low_sentinel:
        return "below 40"
    if reading.is_sensor_high_sentinel:
        return "above 400"
    return f"{reading.mgdl} {UNIT}"

"""Glucose readings and how we parse them from Nightscout.

This module is pure logic: no network, no clock, no I/O. Everything that
touches the outside world lives in the infrastructure layer, so the rules
here can be tested exhaustively with plain data.

Safety note: a reading that fails validation is rejected, never "fixed up".
Showing a wrong number is worse than showing no number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

# Dexcom sensors report 40-400 mg/dL. Nightscout stores out-of-range values
# as 39 ("LOW") and 401 ("HIGH") sentinels, so those are valid inputs too.
SENSOR_MIN_MGDL = 39
SENSOR_MAX_MGDL = 401


class Trend(Enum):
    """Direction of change, using Nightscout's direction strings."""

    DOUBLE_UP = "DoubleUp"
    SINGLE_UP = "SingleUp"
    FORTY_FIVE_UP = "FortyFiveUp"
    FLAT = "Flat"
    FORTY_FIVE_DOWN = "FortyFiveDown"
    SINGLE_DOWN = "SingleDown"
    DOUBLE_DOWN = "DoubleDown"
    UNKNOWN = "Unknown"

    @property
    def arrow(self) -> str:
        """Plain-text arrow that renders on any display, including e-ink."""
        return _ARROWS[self]


_ARROWS = {
    Trend.DOUBLE_UP: "^^",
    Trend.SINGLE_UP: "^",
    Trend.FORTY_FIVE_UP: "/",
    Trend.FLAT: "->",
    Trend.FORTY_FIVE_DOWN: "\\",
    Trend.SINGLE_DOWN: "v",
    Trend.DOUBLE_DOWN: "vv",
    Trend.UNKNOWN: "?",
}


class InvalidReadingError(ValueError):
    """Raised when a Nightscout entry cannot be trusted as a glucose reading."""


@dataclass(frozen=True)
class GlucoseReading:
    """One sensor glucose value at one moment in time."""

    mgdl: int
    timestamp: datetime  # always timezone-aware UTC
    trend: Trend

    @property
    def is_sensor_low_sentinel(self) -> bool:
        """True when the sensor reported below its measurable range."""
        return self.mgdl <= SENSOR_MIN_MGDL

    @property
    def is_sensor_high_sentinel(self) -> bool:
        """True when the sensor reported above its measurable range."""
        return self.mgdl >= SENSOR_MAX_MGDL


def parse_entry(entry: dict) -> GlucoseReading:
    """Turn one Nightscout `/api/v1/entries` record into a GlucoseReading.

    Raises InvalidReadingError for anything we can't trust.
    """
    if not isinstance(entry, dict):
        raise InvalidReadingError("entry is not an object")

    if entry.get("type", "sgv") != "sgv":
        raise InvalidReadingError(f"not a sensor glucose entry: {entry.get('type')!r}")

    sgv = entry.get("sgv")
    # bool is a subclass of int in Python, so rule it out explicitly.
    if isinstance(sgv, bool) or not isinstance(sgv, (int, float)):
        raise InvalidReadingError(f"sgv missing or not a number: {sgv!r}")
    if sgv != int(sgv):
        raise InvalidReadingError(f"sgv is not a whole number: {sgv!r}")
    mgdl = int(sgv)
    if not SENSOR_MIN_MGDL <= mgdl <= SENSOR_MAX_MGDL:
        raise InvalidReadingError(f"sgv outside sensor range: {mgdl}")

    date_ms = entry.get("date")
    if isinstance(date_ms, bool) or not isinstance(date_ms, (int, float)) or date_ms <= 0:
        raise InvalidReadingError(f"date missing or invalid: {date_ms!r}")
    timestamp = datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc)

    try:
        trend = Trend(entry.get("direction", "Unknown"))
    except ValueError:
        # An unrecognized arrow is not a reason to drop the number itself.
        trend = Trend.UNKNOWN

    return GlucoseReading(mgdl=mgdl, timestamp=timestamp, trend=trend)


def parse_entries(entries: list) -> list[GlucoseReading]:
    """Parse a list of entries, skipping bad ones, newest first."""
    readings = []
    for entry in entries or []:
        try:
            readings.append(parse_entry(entry))
        except InvalidReadingError:
            continue
    readings.sort(key=lambda r: r.timestamp, reverse=True)
    return readings

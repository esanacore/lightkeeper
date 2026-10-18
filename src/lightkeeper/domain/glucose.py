"""Glucose readings and how we parse them from Nightscout.

This module is pure logic: no network, no clock, no I/O. Everything that
touches the outside world lives in the infrastructure layer, so the rules
here can be tested exhaustively with plain data.

Safety note: a reading that fails validation is rejected, never "fixed up".
Showing a wrong number is worse than showing no number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

# Dexcom sensors report 40-400 mg/dL. Nightscout stores out-of-range values
# as 39 ("LOW") and 401 ("HIGH") sentinels, so those are valid inputs too.
SENSOR_MIN_MGDL = 39
SENSOR_MAX_MGDL = 401

# Plausible window for an entry's `date` (Unix milliseconds). Anything outside
# is rejected before it reaches the clock library: a value in seconds instead
# of milliseconds lands in 1970 and would otherwise show as STALE, and a
# huge value would raise an unexpected error from datetime instead of a clean
# InvalidReadingError. 2000-01-01T00:00Z to 2100-01-01T00:00Z.
MIN_DATE_MS = 946_684_800_000
MAX_DATE_MS = 4_102_444_800_000


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


def parse_entry(entry: object) -> GlucoseReading:
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
    # Range-check the raw number before int(): int(nan) and int(inf) raise
    # ValueError/OverflowError, which would escape as an unexpected failure.
    if not math.isfinite(sgv) or not SENSOR_MIN_MGDL <= sgv <= SENSOR_MAX_MGDL:
        raise InvalidReadingError(f"sgv outside sensor range: {sgv!r}")
    if sgv != int(sgv):
        raise InvalidReadingError(f"sgv is not a whole number: {sgv!r}")
    mgdl = int(sgv)

    date_ms = entry.get("date")
    if isinstance(date_ms, bool) or not isinstance(date_ms, (int, float)):
        raise InvalidReadingError(f"date missing or invalid: {date_ms!r}")
    if not math.isfinite(date_ms) or not MIN_DATE_MS <= date_ms <= MAX_DATE_MS:
        raise InvalidReadingError(f"date outside plausible range: {date_ms!r}")
    timestamp = datetime.fromtimestamp(date_ms / 1000, tz=UTC)

    try:
        trend = Trend(entry.get("direction", "Unknown"))
    except ValueError:
        # An unrecognized arrow is not a reason to drop the number itself.
        trend = Trend.UNKNOWN

    return GlucoseReading(mgdl=mgdl, timestamp=timestamp, trend=trend)


def parse_entries(entries: list[Any] | None) -> list[GlucoseReading]:
    """Parse a list of entries, skipping bad ones, newest first.

    One malformed entry must never take the good ones down with it: whatever
    parse_entry raises, the rest of the list is still used. When two entries
    share a timestamp (several uploaders feeding one Nightscout), the lower
    value wins, which is the conservative choice for a glucose display.
    """
    readings = []
    for entry in entries or []:
        try:
            readings.append(parse_entry(entry))
        except (InvalidReadingError, ValueError, OverflowError, OSError, TypeError):
            continue
    readings.sort(key=lambda r: (-r.timestamp.timestamp(), r.mgdl))
    return readings

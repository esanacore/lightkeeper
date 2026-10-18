"""Classify the latest reading into a display status.

The single most important rule in this file: old data is never shown as
if it were current. A number that looks fine but is 30 minutes old is the
most dangerous thing a glucose display can show, so staleness is checked
before anything else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from lightkeeper.domain.glucose import GlucoseReading

# A reading timestamped this far in the future means a clock is wrong
# somewhere, so we refuse to trust it.
MAX_FUTURE_SKEW = timedelta(minutes=2)


class Level(Enum):
    """Display status, ordered roughly by urgency."""

    NO_DATA = "NO DATA"
    STALE = "STALE"
    URGENT_LOW = "URGENT LOW"
    LOW = "LOW"
    IN_RANGE = "IN RANGE"
    HIGH = "HIGH"
    URGENT_HIGH = "URGENT HIGH"

    @property
    def needs_attention(self) -> bool:
        """True for anything a person should look at right now."""
        return self is not Level.IN_RANGE


@dataclass(frozen=True)
class Thresholds:
    """Alert thresholds in mg/dL plus the staleness limit.

    Defaults follow common clinical targets (70-180 mg/dL range). They are
    display settings only and must be agreed with Kaitlin and her care team.
    """

    urgent_low: int = 55
    low: int = 70
    high: int = 180
    urgent_high: int = 250
    stale_after: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if not 40 <= self.urgent_low < self.low < self.high < self.urgent_high <= 400:
            raise ValueError(
                "thresholds must satisfy 40 <= urgent_low < low < high < urgent_high <= 400"
            )
        if self.stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")


@dataclass(frozen=True)
class Status:
    """What a display should show, derived from a reading and the time."""

    level: Level
    reading: GlucoseReading | None
    age: timedelta | None

    @property
    def age_minutes(self) -> int | None:
        if self.age is None:
            return None
        return int(self.age.total_seconds() // 60)


def classify(reading: GlucoseReading | None, now: datetime, thresholds: Thresholds) -> Status:
    """Decide the display status for the newest reading at time `now`."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if reading is None:
        return Status(level=Level.NO_DATA, reading=None, age=None)

    age = now - reading.timestamp

    # Checked first, on purpose: stale or future-dated data is never trusted.
    if age > thresholds.stale_after or age < -MAX_FUTURE_SKEW:
        return Status(level=Level.STALE, reading=reading, age=age)

    mgdl = reading.mgdl
    if mgdl <= thresholds.urgent_low:
        level = Level.URGENT_LOW
    elif mgdl < thresholds.low:
        level = Level.LOW
    elif mgdl >= thresholds.urgent_high:
        level = Level.URGENT_HIGH
    elif mgdl > thresholds.high:
        level = Level.HIGH
    else:
        level = Level.IN_RANGE

    return Status(level=level, reading=reading, age=max(age, timedelta(0)))

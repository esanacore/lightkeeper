"""The display status as a plain JSON-ready dict.

One payload feeds both `--json PATH` and the Home Assistant publisher
(ADR-0010), so every consumer sees exactly what the displays show.

Safety: `mgdl` is a number only for a fresh, measured reading. When the level
is STALE or NO DATA, or the sensor reported a LOW/HIGH sentinel, it is None,
so a dashboard or automation reading the number alone cannot mistake an old
or out-of-range value for a current one (HAZ-013). The last value is still
there, labeled as such, in `last_mgdl`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lightkeeper.application.monitor import render_lines
from lightkeeper.domain.status import Level, Status

# Bump when a field changes meaning or disappears; adding a field does not.
PAYLOAD_VERSION = 1


def status_payload(status: Status, error: str | None, now: datetime) -> dict[str, Any]:
    """Return the status at `now` as a dict of JSON-safe values."""
    reading = status.reading
    measured = reading is not None and not (
        reading.is_sensor_low_sentinel or reading.is_sensor_high_sentinel
    )
    trustworthy = status.level not in (Level.STALE, Level.NO_DATA)
    return {
        "version": PAYLOAD_VERSION,
        "level": status.level.value,
        "mgdl": reading.mgdl if reading is not None and measured and trustworthy else None,
        "last_mgdl": reading.mgdl if reading is not None else None,
        "trend": reading.trend.value if reading is not None else None,
        "age_minutes": status.age_minutes,
        "needs_attention": status.level.needs_attention,
        "error": error,
        "lines": render_lines(status, error),
        "generated_at": now.astimezone(UTC).isoformat(timespec="seconds"),
    }

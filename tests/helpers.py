"""Shared test helpers: build Nightscout-shaped entries at a fixed clock."""

from datetime import UTC, datetime, timedelta

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def entry(mgdl=120, minutes_ago=0, direction="Flat", **extra):
    when = NOW - timedelta(minutes=minutes_ago)
    data = {
        "type": "sgv",
        "sgv": mgdl,
        "date": int(when.timestamp() * 1000),
        "direction": direction,
    }
    data.update(extra)
    return data


class FakeSource:
    """Stands in for NightscoutClient. Returns entries or raises."""

    def __init__(self, entries=None, error=None):
        self.entries = entries or []
        self.error = error
        self.calls = 0

    def fetch_entries(self, count=12):
        self.calls += 1
        if self.error:
            raise self.error
        return self.entries

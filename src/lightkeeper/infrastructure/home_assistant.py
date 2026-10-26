"""Publish the display status to Home Assistant over MQTT discovery (ADR-0010).

Three sensors share one JSON state topic: the level (the displays' own
classification), glucose in mg/dL, and the reading's age in minutes.

How a dead or stuck publisher is kept from looking alive (HAZ-013):
- A Last Will marks the availability topic `offline` when the connection
  drops; the keepalive bounds how long a silent power loss takes to notice.
- `expire_after` makes the entities unavailable if updates simply stop.
- State messages are never retained, so a broker replaying them to a
  restarted Home Assistant cannot make an old level look new. Only the
  discovery configs and the availability flag are retained.
"""

from __future__ import annotations

import json
import re
from typing import Any

from lightkeeper import __version__
from lightkeeper.infrastructure.mqtt import MqttError, MqttPublisher, Will

ONLINE = b"online"
OFFLINE = b"offline"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def expire_after_seconds(interval_seconds: int, stale_seconds: int) -> int:
    """Three refresh intervals (at least 3 minutes), never longer than the stale limit."""
    return min(stale_seconds, max(3 * interval_seconds, 180))


def keepalive_seconds(interval_seconds: int) -> int:
    """Twice the refresh interval (at least a minute): one publish per cycle keeps it open."""
    return min(0xFFFF, max(60, 2 * interval_seconds))


class HomeAssistantPublisher:
    """Keeps one MQTT connection and publishes each status to it."""

    def __init__(
        self,
        mqtt: MqttPublisher,
        interval_seconds: int,
        stale_seconds: int,
        node_id: str = "lightkeeper",
        discovery_prefix: str = "homeassistant",
    ) -> None:
        """Configure the topics; nothing is sent until the first publish."""
        if not _SAFE_ID.match(node_id):
            raise ValueError("the node id may contain only letters, digits, '_' and '-'")
        if not _SAFE_ID.match(discovery_prefix):
            raise ValueError("the discovery prefix may contain only letters, digits, '_' and '-'")
        self._mqtt = mqtt
        self.node_id = node_id
        self.discovery_prefix = discovery_prefix
        self.state_topic = f"lightkeeper/{node_id}/state"
        self.availability_topic = f"lightkeeper/{node_id}/availability"
        self.expire_after = expire_after_seconds(interval_seconds, stale_seconds)
        self.keepalive = keepalive_seconds(interval_seconds)

    def discovery_messages(self) -> list[tuple[str, dict[str, Any]]]:
        """(topic, config) for each sensor Home Assistant should create."""
        device = {
            "identifiers": [self.node_id],
            "name": "Lightkeeper",
            "manufacturer": "Lightkeeper",
            "model": "Read-only glucose display (secondary; confirm on the primary app)",
            "sw_version": __version__,
        }
        common = {
            "state_topic": self.state_topic,
            "json_attributes_topic": self.state_topic,
            "availability_topic": self.availability_topic,
            "payload_available": ONLINE.decode(),
            "payload_not_available": OFFLINE.decode(),
            "expire_after": self.expire_after,
            "device": device,
        }
        sensors = {
            "level": {
                "name": "Glucose level",
                "value_template": "{{ value_json.level }}",
                "icon": "mdi:diabetes",
            },
            "glucose": {
                "name": "Glucose",
                # None when STALE, NO DATA, or a sensor sentinel: Home Assistant
                # then shows unknown instead of an old or unmeasured number.
                "value_template": "{{ value_json.mgdl }}",
                "unit_of_measurement": "mg/dL",
                "state_class": "measurement",
                "icon": "mdi:water",
            },
            "age": {
                "name": "Glucose reading age",
                "value_template": "{{ value_json.age_minutes }}",
                "unit_of_measurement": "min",
                "icon": "mdi:clock-outline",
            },
        }
        return [
            (
                f"{self.discovery_prefix}/sensor/{self.node_id}/{key}/config",
                {**common, **extra, "unique_id": f"{self.node_id}_{key}"},
            )
            for key, extra in sensors.items()
        ]

    def _ensure_connected(self) -> None:
        if self._mqtt.connected:
            return
        self._mqtt.connect(self.keepalive, Will(self.availability_topic, OFFLINE, retain=True))
        for topic, config in self.discovery_messages():
            self._mqtt.publish(topic, json.dumps(config, sort_keys=True).encode(), retain=True)
        self._mqtt.publish(self.availability_topic, ONLINE, retain=True)

    def publish(self, payload: dict[str, Any]) -> None:
        """Publish one status. Connects (or reconnects) first when needed.

        Raises MqttError on failure; the connection is then closed and the
        next call starts over.
        """
        self._ensure_connected()
        # Never retained (HAZ-013): a replay must not freshen an old level.
        self._mqtt.publish(self.state_topic, json.dumps(payload, sort_keys=True).encode())

    def finish(self, offline: bool) -> None:
        """End the session.

        With `offline`, mark the entities unavailable first: the `--watch`
        loop is stopping. Without it (a one-shot run from cron), leave them
        available and let `expire_after` catch a schedule that stops.
        """
        if not self._mqtt.connected:
            return
        if offline:
            try:
                self._mqtt.publish(self.availability_topic, OFFLINE, retain=True)
            except MqttError:  # shutting down; the broker's will covers it
                self._mqtt.close()
                return
        self._mqtt.disconnect()

"""Settings from the environment, checked once at startup (NFR-002).

Part of the composition root, with cli.py and the desktop window, and outside
the layers: this is where os.environ is read and turned into the domain's
thresholds, the entry source, and the Home Assistant publisher.

Every unusable setting raises ConfigError, whose message names the variable,
the value, and the clash, for example "LK_LOW=200 must be below LK_HIGH=180
(the default)", so a front end can print it as it is and exit 2. An empty
variable means the default, as an unset one does. NIGHTSCOUT_URL and the
secrets are named but their values are never echoed. Every variable is in
docs/ENV_VARS.md.
"""

from __future__ import annotations

import argparse
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from lightkeeper.application.monitor import EntrySource
from lightkeeper.domain.glucose import SENSOR_MAX_MGDL, SENSOR_MIN_MGDL
from lightkeeper.domain.status import Thresholds
from lightkeeper.infrastructure.home_assistant import HomeAssistantPublisher
from lightkeeper.infrastructure.mqtt import LOCAL_HOSTS, MqttPublisher
from lightkeeper.infrastructure.nightscout import NightscoutClient

# The canned reading --demo shows unless told otherwise.
DEMO_MGDL = 112
DEMO_MINUTES_AGO = 3
DEMO_TREND = "Flat"

# The sensor's measurable range; 39 and 401 are its LOW and HIGH sentinels.
LOWEST_THRESHOLD = SENSOR_MIN_MGDL + 1
HIGHEST_THRESHOLD = SENSOR_MAX_MGDL - 1

# Nine digits is far beyond any setting here, and keeps int() and timedelta safe.
_WHOLE_NUMBER = re.compile(r"[+-]?[0-9]{1,9}")
_DIGITS = re.compile(r"[+-]?[0-9]+")
# The same rule HomeAssistantPublisher enforces, checked here to name the variable.
_MQTT_ID = re.compile(r"[A-Za-z0-9_-]+")
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})

# Builds the Nightscout source from (url, token=...); the CLI passes its own.
ClientFactory = Callable[..., EntrySource]


class ConfigError(ValueError):
    """A setting that cannot be used. The message names the variable and the clash."""


class DemoSource:
    """Canned readings for trying the display with no Nightscout at all."""

    def __init__(
        self,
        mgdl: int = DEMO_MGDL,
        minutes_ago: int = DEMO_MINUTES_AGO,
        direction: str = DEMO_TREND,
    ) -> None:
        """Serve one reading of `mgdl`, `minutes_ago` minutes old, with `direction`."""
        self._mgdl = mgdl
        self._minutes_ago = minutes_ago
        self._direction = direction

    def fetch_entries(self, count: int = 12) -> list[Any]:
        """Return a single Nightscout-shaped entry; `count` is ignored."""
        when = datetime.now(UTC) - timedelta(minutes=self._minutes_ago)
        return [
            {
                "type": "sgv",
                "sgv": self._mgdl,
                "date": int(when.timestamp() * 1000),
                "direction": self._direction,
            }
        ]


def _raw(name: str) -> str:
    return os.environ.get(name, "").strip()


def _shown(raw: str) -> str:
    """Show a value as typed: a number bare, anything else quoted, a long one cut short."""
    if len(raw) > 24:
        return repr(raw[:24]) + "..."
    return raw if _DIGITS.fullmatch(raw) else repr(raw)


def int_env(name: str, default: int) -> int:
    """Read a whole-number variable; empty or unset means `default`."""
    raw = _raw(name)
    if raw == "":
        return default
    if not _DIGITS.fullmatch(raw):
        raise ConfigError(f"{name}={_shown(raw)} must be a whole number")
    if not _WHOLE_NUMBER.fullmatch(raw):
        raise ConfigError(f"{name}={_shown(raw)} is far too large")
    return int(raw)


def bool_env(name: str, default: bool) -> bool:
    """Read a true or false variable; empty or unset means `default`."""
    raw = _raw(name)
    if raw == "":
        return default
    if raw.lower() in _TRUE:
        return True
    if raw.lower() in _FALSE:
        return False
    raise ConfigError(f"{name}={_shown(raw)} must be true or false")


def _setting(name: str, value: int) -> str:
    """`NAME=value`, marked when the value is the default because NAME is unset."""
    return f"{name}={value}" + ("" if _raw(name) else " (the default)")


def thresholds_from_env() -> Thresholds:
    """Build thresholds from the LK_* variables (see docs/ENV_VARS.md).

    Raises ConfigError naming the first clash, in the order a person reads
    the thresholds: the urgent low floor, each pair from low to high, the
    urgent high ceiling, then the stale limit. Together these are exactly
    the rules `Thresholds` enforces (tests/test_config.py checks both agree).
    """
    default = Thresholds()
    names = ("LK_URGENT_LOW", "LK_LOW", "LK_HIGH", "LK_URGENT_HIGH")
    defaults = (default.urgent_low, default.low, default.high, default.urgent_high)
    values = [int_env(name, value) for name, value in zip(names, defaults, strict=True)]
    shown = [_setting(name, value) for name, value in zip(names, values, strict=True)]
    if values[0] < LOWEST_THRESHOLD:
        raise ConfigError(
            f"{shown[0]} must be at least {LOWEST_THRESHOLD} mg/dL, the lowest a sensor measures"
        )
    for i in range(len(values) - 1):
        if values[i] >= values[i + 1]:
            raise ConfigError(f"{shown[i]} must be below {shown[i + 1]}")
    if values[-1] > HIGHEST_THRESHOLD:
        raise ConfigError(
            f"{shown[-1]} must be at most {HIGHEST_THRESHOLD} mg/dL, the highest a sensor measures"
        )
    stale = int_env("LK_STALE_MINUTES", int(default.stale_after.total_seconds()) // 60)
    if stale < 1:
        raise ConfigError(f"{_setting('LK_STALE_MINUTES', stale)} must be at least 1 minute")
    urgent_low, low, high, urgent_high = values
    return Thresholds(
        urgent_low=urgent_low,
        low=low,
        high=high,
        urgent_high=urgent_high,
        stale_after=timedelta(minutes=stale),
    )


def home_assistant_from_env(
    interval_seconds: int, thresholds: Thresholds
) -> HomeAssistantPublisher | None:
    """Build the Home Assistant publisher from LK_MQTT_* variables, or None when unset.

    Raises ConfigError for an unusable configuration (see docs/ENV_VARS.md).
    The password is never part of a message.
    """
    host = _raw("LK_MQTT_HOST")
    if not host:
        return None
    tls = bool_env("LK_MQTT_TLS", True)
    port = int_env("LK_MQTT_PORT", 8883 if tls else 1883)
    if not 1 <= port <= 0xFFFF:
        raise ConfigError(f"LK_MQTT_PORT={port} must be a port number from 1 to 65535")
    if not tls and host.lower() not in LOCAL_HOSTS:
        raise ConfigError(
            f"LK_MQTT_TLS=false is allowed only for a broker on this machine (localhost, "
            f"127.0.0.1 or ::1), not LK_MQTT_HOST={host}: the password and glucose readings "
            "would cross the network unencrypted"
        )
    node_id = _raw("LK_MQTT_NODE_ID") or "lightkeeper"
    prefix = _raw("LK_MQTT_DISCOVERY_PREFIX") or "homeassistant"
    for name, value in (("LK_MQTT_NODE_ID", node_id), ("LK_MQTT_DISCOVERY_PREFIX", prefix)):
        if not _MQTT_ID.fullmatch(value):
            raise ConfigError(
                f"{name}={_shown(value)} may contain only letters, digits, '_' and '-'"
            )
    username = os.environ.get("LK_MQTT_USERNAME") or None
    password = os.environ.get("LK_MQTT_PASSWORD") or None
    if password is not None and username is None:
        raise ConfigError(
            "LK_MQTT_PASSWORD is set but LK_MQTT_USERNAME is not: MQTT 3.1.1 sends a "
            "password only with a user name"
        )
    mqtt = MqttPublisher(
        host,
        port,
        client_id=f"lightkeeper-{node_id}",
        username=username,
        password=password,
        tls=tls,
    )
    return HomeAssistantPublisher(
        mqtt,
        interval_seconds=interval_seconds,
        stale_seconds=int(thresholds.stale_after.total_seconds()),
        node_id=node_id,
        discovery_prefix=prefix,
    )


def source_from_env(
    args: argparse.Namespace, client_factory: ClientFactory = NightscoutClient
) -> EntrySource:
    """Return the entry source: canned data with --demo, else Nightscout from the environment.

    `args` needs `demo`; `demo_mgdl`, `demo_minutes_ago` and `demo_trend` are
    optional, and None or missing means the canned default. Without --demo
    the demo options are ignored here, so canned data never stands in for
    Nightscout. Raises ConfigError when NIGHTSCOUT_URL is missing or unusable;
    the message names the variable and never echoes its value.
    """
    if getattr(args, "demo", False):
        mgdl = getattr(args, "demo_mgdl", None)
        minutes_ago = getattr(args, "demo_minutes_ago", None)
        trend = getattr(args, "demo_trend", None)
        return DemoSource(
            mgdl=DEMO_MGDL if mgdl is None else mgdl,
            minutes_ago=DEMO_MINUTES_AGO if minutes_ago is None else minutes_ago,
            direction=DEMO_TREND if trend is None else trend,
        )
    url = _raw("NIGHTSCOUT_URL")
    if not url:
        raise ConfigError(
            "NIGHTSCOUT_URL is not set: set it to your Nightscout site's https address "
            "(see docs/ENV_VARS.md), or use --demo"
        )
    token = _raw("NIGHTSCOUT_TOKEN") or None
    try:
        return client_factory(url, token=token)
    except ValueError as exc:
        raise ConfigError(str(exc)) from None

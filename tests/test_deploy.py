"""HAZ-002 / HAZ-013: the systemd service and the sd_notify watchdog.

The unit file in deploy/ is checked against the real CLI so the two cannot
drift apart, and the notifier is checked both with a fake sender (any OS) and
over a real Unix datagram socket (Linux, where CI runs).
"""

import shlex
import socket
import sys
from pathlib import Path

import pytest

from lightkeeper import cli
from lightkeeper.infrastructure.systemd_notify import SystemdNotifier, notify_address

UNIT = Path(__file__).resolve().parent.parent / "deploy" / "lightkeeper.service"


def parse_unit(text):
    """{section: {key: [values]}}; systemd allows a key to repeat."""
    sections, current = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
            continue
        key, _, value = line.partition("=")
        current.setdefault(key.strip(), []).append(value.strip())
    return sections


SERVICE = parse_unit(UNIT.read_text(encoding="utf-8"))["Service"]


def one(key):
    values = SERVICE[key]
    assert len(values) == 1, key
    return values[0]


# --- the unit file -------------------------------------------------------------


def test_haz002_service_uses_the_watchdog_and_restarts():
    assert one("Type") == "notify"
    assert one("NotifyAccess") == "main"
    assert one("Restart") == "always"
    exec_args = shlex.split(one("ExecStart"))
    args = cli.build_parser().parse_args(exec_args[3:])
    assert exec_args[1:3] == ["-m", "lightkeeper"]
    assert args.watch
    # Room for two refresh intervals plus the Nightscout and MQTT timeouts.
    assert int(one("WatchdogSec")) >= 2 * args.interval + 30


def test_haz013_service_stop_runs_the_clean_shutdown():
    """SIGINT reaches Python as KeyboardInterrupt, so Home Assistant gets `offline`."""
    assert one("KillSignal") == "SIGINT"
    assert int(one("TimeoutStopSec")) >= 10


def test_haz002_service_writes_only_its_runtime_directory():
    args = cli.build_parser().parse_args(shlex.split(one("ExecStart"))[3:])
    assert one("RuntimeDirectory") == "lightkeeper"
    assert args.svg.startswith("/run/lightkeeper/")
    assert args.json.startswith("/run/lightkeeper/")


def test_nfr001_service_is_sandboxed_and_unprivileged():
    assert one("User") not in ("root", "pi")
    assert one("EnvironmentFile") == "/etc/lightkeeper.env"
    expected = {
        "NoNewPrivileges": "yes",
        "CapabilityBoundingSet": "",
        "ProtectSystem": "strict",
        "ProtectHome": "yes",
        "PrivateTmp": "yes",
        "PrivateDevices": "yes",
        "RestrictSUIDSGID": "yes",
        "MemoryDenyWriteExecute": "yes",
        "SystemCallArchitectures": "native",
    }
    for key, value in expected.items():
        assert one(key) == value, key
    # Outbound network for Nightscout and MQTT, AF_UNIX for the notify socket.
    assert set(one("RestrictAddressFamilies").split()) == {"AF_INET", "AF_INET6", "AF_UNIX"}


# --- the notifier --------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "address"),
    [
        (None, None),
        ("", None),
        ("/run/systemd/notify", "/run/systemd/notify"),
        ("@systemd-notify", "\0systemd-notify"),
        ("vsock:2:1234", None),
    ],
)
def test_haz002_notify_socket_addresses(raw, address):
    assert notify_address(raw) == address


class Recorder:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def __call__(self, message, address):
        if self.fail:
            raise OSError("no listener")
        self.sent.append((message.decode(), address))


def test_haz002_messages_follow_the_sd_notify_format():
    rec = Recorder()
    n = SystemdNotifier("/run/systemd/notify", sender=rec)
    assert n.enabled
    n.ready("starting")
    n.alive("IN RANGE")
    n.stopping()
    n.notify()  # nothing to send
    assert rec.sent == [
        ("READY=1\nSTATUS=starting", "/run/systemd/notify"),
        ("WATCHDOG=1\nSTATUS=IN RANGE", "/run/systemd/notify"),
        ("STOPPING=1\nSTATUS=stopping", "/run/systemd/notify"),
    ]


def test_haz002_a_newline_in_a_value_cannot_inject_a_field():
    rec = Recorder()
    SystemdNotifier("/s", sender=rec).notify(STATUS="LOW\nWATCHDOG=1")
    assert rec.sent == [("STATUS=LOW WATCHDOG=1", "/s")]


def test_haz002_outside_systemd_nothing_is_sent(monkeypatch):
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    rec = Recorder()
    n = SystemdNotifier(sender=rec)
    assert not n.enabled
    n.alive("IN RANGE")
    assert rec.sent == []


def test_haz002_a_failed_send_never_breaks_the_display():
    SystemdNotifier("/s", sender=Recorder(fail=True)).alive("IN RANGE")


def test_haz002_notify_socket_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("NOTIFY_SOCKET", "@lk-test")
    rec = Recorder()
    SystemdNotifier(sender=rec).ready("starting")
    assert rec.sent[0][1] == "\0lk-test"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Unix datagram sockets")
def test_haz002_real_datagram_reaches_a_listening_socket(tmp_path):
    path = str(tmp_path / "notify")
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
        listener.bind(path)
        listener.settimeout(3)
        SystemdNotifier(path).alive("URGENT LOW")
        assert listener.recv(256) == b"WATCHDOG=1\nSTATUS=URGENT LOW"


# --- the CLI pets the watchdog once per cycle ----------------------------------


def test_haz002_watch_loop_pets_the_watchdog_every_cycle(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(cli, "SystemdNotifier", lambda: SystemdNotifier("/s", sender=rec))
    calls = {"n": 0}

    def fake_sleep(seconds):
        calls["n"] += 1
        if calls["n"] >= 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    assert cli.main(["--demo", "--watch"]) == 0
    messages = [m for m, _ in rec.sent]
    assert messages[0] == "READY=1\nSTATUS=starting"
    assert messages[1:4] == ["WATCHDOG=1\nSTATUS=IN RANGE"] * 3
    assert messages[-1] == "STOPPING=1\nSTATUS=stopping"


def test_haz002_status_line_reports_an_unreachable_nightscout(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(cli, "SystemdNotifier", lambda: SystemdNotifier("/s", sender=rec))
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")

    class Down:
        def fetch_entries(self, count=12):
            raise OSError("refused")

    monkeypatch.setattr(cli, "NightscoutClient", lambda url, token=None: Down())
    assert cli.main([]) == 1
    assert "WATCHDOG=1\nSTATUS=NO DATA, Nightscout unreachable" in [m for m, _ in rec.sent]

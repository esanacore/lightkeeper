"""FR-006: the CLI runs offline in demo mode and signals attention via exit code.

Honest output: stdout is exactly the vector lines unless an interactive
terminal runs --watch; what failed, and which setting to check, goes to
stderr once per change; Ctrl+C in a one-shot run exits 130 and a bad setting
exits 2, never 0; canned data needs an explicit --demo; exported panel images
always carry their stamp (HAZ-014).
"""

import errno
import io
import json
import os
import socket
import types
import urllib.error
import urllib.parse

import pytest

from lightkeeper import cli, config
from lightkeeper.application.status_payload import status_payload
from lightkeeper.domain.glucose import Trend, parse_entries
from lightkeeper.domain.status import Thresholds, classify
from lightkeeper.infrastructure import nightscout, terminal_view
from lightkeeper.infrastructure.epaper_bitmap import render_bitmap, stamp_text
from lightkeeper.infrastructure.nightscout import NightscoutClient, NightscoutError
from lightkeeper.infrastructure.panel_profiles import resolve
from tests.fake_broker import FakeBroker
from tests.helpers import NOW, FakeSource, entry
from tests.test_epaper_bitmap import decode_bmp, decode_png
from tests.test_vectors import VECTORS, raw_entries

SEPARATOR = "-" * 24 + "\n"
FRESH = "IN RANGE\n112 mg/dL ->\n3 min ago\n"
FAILING = FRESH + "Nightscout unreachable\n"
TOKEN = "readable-s3cret-token"
REFUSED = (
    "lightkeeper: Nightscout refused the token (HTTP 401). Check NIGHTSCOUT_TOKEN is a "
    "readable token, never the API secret"
)
DNS = (
    "lightkeeper: Could not find Nightscout's address (the DNS lookup failed). Check "
    "NIGHTSCOUT_URL is spelled right and that this device is online"
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in [
        "NIGHTSCOUT_URL",
        "NIGHTSCOUT_TOKEN",
        "LK_URGENT_LOW",
        "LK_LOW",
        "LK_HIGH",
        "LK_URGENT_HIGH",
        "LK_STALE_MINUTES",
        "LK_MQTT_HOST",
        "LK_MQTT_PORT",
        "LK_MQTT_TLS",
        "LK_MQTT_USERNAME",
        "LK_MQTT_PASSWORD",
        "LK_MQTT_DISCOVERY_PREFIX",
        "LK_MQTT_NODE_ID",
        "NO_COLOR",
        "TERM",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("COLUMNS", "80")  # the frame's footer, and --help, at a known width


def test_fr006_demo_in_range_exits_zero(capsys):
    assert cli.main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "IN RANGE" in out
    assert "112 mg/dL" in out


def test_fr006_demo_low_exits_one(capsys):
    assert cli.main(["--demo", "--demo-mgdl", "60"]) == 1
    assert "LOW" in capsys.readouterr().out


def test_fr006_demo_stale_exits_one(capsys):
    assert cli.main(["--demo", "--demo-minutes-ago", "40"]) == 1
    assert "STALE" in capsys.readouterr().out


def test_fr006_missing_url_is_a_clear_error(capsys):
    assert cli.main([]) == 2
    assert "NIGHTSCOUT_URL" in capsys.readouterr().err


def test_nfr001_http_url_rejected_at_startup(monkeypatch, capsys):
    monkeypatch.setenv("NIGHTSCOUT_URL", "http://ns.example.com")
    assert cli.main([]) == 2
    assert "https" in capsys.readouterr().err


def test_fr005_unreachable_nightscout_reports_no_data(monkeypatch, capsys):
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.invalid")
    monkeypatch.setenv("NIGHTSCOUT_TOKEN", "readable-secret")

    def boom(url, headers, timeout):
        raise OSError(f"no route to {url}")

    monkeypatch.setattr(cli.NightscoutClient, "__init__", _client_init_with(boom))
    assert cli.main([]) == 1
    out = capsys.readouterr().out
    assert "NO DATA" in out and "Nightscout unreachable" in out
    assert "readable-secret" not in out


def _client_init_with(fetcher):
    original = cli.NightscoutClient.__init__

    def init(self, base_url, token=None, **kwargs):
        original(self, base_url, token=token, fetcher=fetcher)

    return init


def test_nfr002_thresholds_from_env(monkeypatch):
    monkeypatch.setenv("LK_LOW", "75")
    monkeypatch.setenv("LK_STALE_MINUTES", "10")
    t = cli.thresholds_from_env()
    assert t.low == 75
    assert t.stale_after.total_seconds() == 600


@pytest.mark.parametrize("name, value", [("LK_LOW", "abc"), ("LK_HIGH", "50")])
def test_nfr002_bad_threshold_env_stops_startup(monkeypatch, capsys, name, value):
    monkeypatch.setenv(name, value)
    assert cli.main(["--demo"]) == 2
    out, err = capsys.readouterr()
    assert out == ""  # nothing is shown with thresholds that cannot be trusted
    assert err.startswith("Configuration error: ") and name in err


def test_fr006_watch_mode_loops_until_interrupted(monkeypatch, capsys):
    calls = {"n": 0}

    def fake_sleep(seconds):
        calls["n"] += 1
        assert seconds >= 15  # never hammer the server
        if calls["n"] >= 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    # Ctrl+C is a clean exit (code 0), not a traceback.
    assert cli.main(["--demo", "--watch", "--interval", "1"]) == 0
    assert capsys.readouterr().out.count("IN RANGE") == 2


def test_haz011_watch_survives_svg_write_failure(monkeypatch, capsys, tmp_path):
    """HAZ-011: a full disk or locked file must not kill the writer process.

    systemd would restart-loop it; without systemd the last image would sit
    on the dashboard looking fresh forever.
    """
    calls = {"n": 0}

    def fake_sleep(seconds):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    missing_dir = tmp_path / "does-not-exist" / "screen.svg"
    assert cli.main(["--demo", "--watch", "--svg", str(missing_dir)]) == 0
    out, err = capsys.readouterr()
    assert out.count("IN RANGE") == 2  # both cycles still rendered
    assert err.count("Could not write") == 2


def test_haz011_run_once_svg_write_failure_is_a_config_error(capsys, tmp_path):
    missing_dir = tmp_path / "does-not-exist" / "screen.svg"
    assert cli.main(["--demo", "--svg", str(missing_dir)]) == 2
    assert "Could not write" in capsys.readouterr().err


# --- --json and Home Assistant (FR-008, ADR-0010) ------------------------------


def test_fr008_json_output_matches_the_screen(tmp_path, capsys):
    target = tmp_path / "status.json"
    assert cli.main(["--demo", "--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["level"] == "IN RANGE"
    assert payload["mgdl"] == 112
    assert payload["lines"] == capsys.readouterr().out.strip().splitlines()
    assert not (tmp_path / "status.json.tmp").exists()


def test_haz011_run_once_json_write_failure_is_a_config_error(capsys, tmp_path):
    missing = tmp_path / "nope" / "status.json"
    assert cli.main(["--demo", "--json", str(missing)]) == 2
    assert "Could not write" in capsys.readouterr().err


def test_fr008_mqtt_is_off_unless_a_host_is_set():
    assert cli.home_assistant_from_env(60, cli.thresholds_from_env()) is None


def test_fr008_mqtt_settings_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("LK_MQTT_HOST", "broker.example.com")
    monkeypatch.setenv("LK_MQTT_USERNAME", "lightkeeper")
    monkeypatch.setenv("LK_MQTT_PASSWORD", "secret")
    monkeypatch.setenv("LK_MQTT_NODE_ID", "bedside")
    monkeypatch.setenv("LK_STALE_MINUTES", "10")
    ha = cli.home_assistant_from_env(60, cli.thresholds_from_env())
    assert ha is not None
    assert ha._mqtt.port == 8883  # TLS by default
    assert ha.node_id == "bedside"
    assert ha.expire_after == 180


def test_fr008_plain_mqtt_to_localhost_defaults_to_port_1883(monkeypatch):
    monkeypatch.setenv("LK_MQTT_HOST", "localhost")
    monkeypatch.setenv("LK_MQTT_TLS", "false")
    ha = cli.home_assistant_from_env(60, cli.thresholds_from_env())
    assert ha._mqtt.port == 1883


@pytest.mark.parametrize(
    ("name", "value"),
    [("LK_MQTT_TLS", "maybe"), ("LK_MQTT_TLS", "off"), ("LK_MQTT_NODE_ID", "bed side")],
)
def test_haz013_unsafe_mqtt_settings_stop_startup(monkeypatch, capsys, name, value):
    monkeypatch.setenv("LK_MQTT_HOST", "broker.example.com")
    monkeypatch.setenv(name, value)
    assert cli.main(["--demo"]) == 2
    assert "Configuration error" in capsys.readouterr().err


class RecordingHA:
    def __init__(self, fail=False, interrupt=False):
        self.fail = fail
        self.interrupt = interrupt
        self.payloads = []
        self.finished = None

    def publish(self, payload):
        if self.interrupt:
            raise KeyboardInterrupt
        if self.fail:
            from lightkeeper.infrastructure.mqtt import MqttError

            raise MqttError("could not reach MQTT broker: refused")
        self.payloads.append(payload)

    def finish(self, offline):
        self.finished = offline


def test_haz013_watch_publishes_each_cycle_and_marks_offline_on_exit(monkeypatch):
    ha = RecordingHA()
    monkeypatch.setattr(cli, "home_assistant_from_env", lambda interval, thresholds: ha)
    calls = {"n": 0}

    def fake_sleep(seconds):
        calls["n"] += 1
        if calls["n"] >= 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    assert cli.main(["--demo", "--watch"]) == 0
    assert [p["level"] for p in ha.payloads] == ["IN RANGE"] * 3
    assert ha.finished is True


def test_haz013_one_shot_publishes_once_and_stays_available(monkeypatch):
    ha = RecordingHA()
    monkeypatch.setattr(cli, "home_assistant_from_env", lambda interval, thresholds: ha)
    assert cli.main(["--demo", "--demo-mgdl", "54"]) == 1
    assert [p["level"] for p in ha.payloads] == ["URGENT LOW"]
    assert ha.finished is False


def test_haz013_publish_failure_never_stops_the_display(monkeypatch, capsys):
    ha = RecordingHA(fail=True)
    monkeypatch.setattr(cli, "home_assistant_from_env", lambda interval, thresholds: ha)
    calls = {"n": 0}

    def fake_sleep(seconds):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    assert cli.main(["--demo", "--watch"]) == 0
    out, err = capsys.readouterr()
    assert out.count("IN RANGE") == 2
    assert err.count("Home Assistant publish failed") == 2


def test_fr008_explicit_tls_true_keeps_port_8883(monkeypatch):
    monkeypatch.setenv("LK_MQTT_HOST", "broker.example.com")
    monkeypatch.setenv("LK_MQTT_TLS", "Yes")
    assert cli.home_assistant_from_env(60, cli.thresholds_from_env())._mqtt.port == 8883


# --- helpers for the honest-output tests ------------------------------------------


class FixedClock:
    """Stands in for `datetime` in cli and config: only `now` is used there."""

    @staticmethod
    def now(tz=None):
        return NOW


def freeze(monkeypatch):
    monkeypatch.setattr(cli, "datetime", FixedClock)
    monkeypatch.setattr(config, "datetime", FixedClock)  # the --demo reading's date


def stop_after(monkeypatch, cycles):
    """Ctrl+C in the `cycles`-th sleep, as a person would press it.

    Only cli's own `time` is replaced, so the fake broker's waits still sleep.
    """
    calls = {"n": 0}

    def fake_sleep(seconds):
        calls["n"] += 1
        if calls["n"] >= cycles:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli, "time", types.SimpleNamespace(sleep=fake_sleep))


def http_error(code):
    return urllib.error.HTTPError(
        "https://ns.example.com/api/v1/entries/sgv.json?count=12", code, "x", {}, None
    )


def scripted(*outcomes):
    """Return a fetcher that answers each call with the next outcome: a body, or an exception."""
    queue = list(outcomes)

    def fetch(url, headers, timeout):
        outcome = queue.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return fetch


OK_BODY = json.dumps([entry(112, minutes_ago=3)]).encode()


def nightscout_with(monkeypatch, fetcher, token=TOKEN):
    """Use the real NightscoutClient, configured from the environment, over `fetcher`."""
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")
    monkeypatch.setenv("NIGHTSCOUT_TOKEN", token)

    def factory(url, token=None):
        return NightscoutClient(url, token=token, fetcher=fetcher)

    monkeypatch.setattr(cli, "NightscoutClient", factory)


def source_is(monkeypatch, source):
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")
    monkeypatch.setattr(cli, "NightscoutClient", lambda url, token=None: source)


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


def on_a_terminal(monkeypatch, vt=True):
    """Make stdout an interactive terminal; `vt` is whether escape codes work on it."""
    tty = FakeTTY()
    monkeypatch.setattr(cli.sys, "stdout", tty)
    monkeypatch.setattr(terminal_view, "enable_vt", lambda: vt)
    return tty


# --- configuration errors exit 2, naming the clash (NFR-002) ------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("abc", "LK_LOW='abc' must be a whole number"),
        ("200", "LK_LOW=200 must be below LK_HIGH=180 (the default)"),
    ],
)
def test_nfr002_bad_lk_low_exits_2_with_the_clash_named(monkeypatch, capsys, value, message):
    monkeypatch.setenv("LK_LOW", value)
    assert cli.main(["--demo"]) == 2
    assert capsys.readouterr() == ("", f"Configuration error: {message}\n")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("abc", "LK_MQTT_PORT='abc' must be a whole number"),
        ("70000", "LK_MQTT_PORT=70000 must be a port number from 1 to 65535"),
    ],
)
def test_nfr002_bad_mqtt_port_exits_2_not_1(monkeypatch, capsys, value, message):
    """It used to leave through SystemExit(str), which exits 1: 'look at me', not 'fix me'."""
    monkeypatch.setenv("LK_MQTT_HOST", "broker.example.com")
    monkeypatch.setenv("LK_MQTT_PORT", value)
    assert cli.main(["--demo"]) == 2
    assert capsys.readouterr().err == f"Configuration error: {message}\n"


def test_nfr002_a_library_value_error_is_still_a_configuration_error(monkeypatch, capsys):
    def refuse(interval, thresholds):
        raise ValueError("the node id may contain only letters, digits, '_' and '-'")

    monkeypatch.setattr(cli, "home_assistant_from_env", refuse)
    assert cli.main(["--demo"]) == 2
    assert capsys.readouterr().err.startswith("Configuration error: the node id")


@pytest.mark.parametrize("panel", ["tiny", "10x10", "5000x5000"])
def test_nfr002_unusable_panel_exits_2(capsys, panel):
    with pytest.raises(SystemExit) as caught:
        cli.main(["--demo", "--png", "x.png", "--panel", panel])
    assert caught.value.code == 2
    assert "argument --panel" in capsys.readouterr().err


# --- canned data only with --demo -----------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "named"),
    [
        (["--demo-mgdl", "62"], "--demo-mgdl needs --demo"),
        (["--demo-minutes-ago", "40"], "--demo-minutes-ago needs --demo"),
        (["--demo-trend", "Flat"], "--demo-trend needs --demo"),
        (
            ["--demo-mgdl", "62", "--demo-trend", "SingleDown", "--watch"],
            "--demo-mgdl and --demo-trend need --demo",
        ),
    ],
)
def test_fr006_demo_flags_need_demo(monkeypatch, capsys, argv, named):
    source = FakeSource([entry(112, minutes_ago=3)])
    source_is(monkeypatch, source)
    with pytest.raises(SystemExit) as caught:
        cli.main(argv)
    assert caught.value.code == 2
    out, err = capsys.readouterr()
    assert out == ""  # neither canned nor real data was shown
    assert named in err and "canned readings are shown only with --demo" in err
    assert source.calls == 0


@pytest.mark.parametrize("trend", list(Trend), ids=[t.value for t in Trend])
def test_fr006_demo_trend_choices(capsys, trend):
    assert cli.main(["--demo", "--demo-trend", trend.value]) == 0
    assert capsys.readouterr().out.splitlines()[1] == f"112 mg/dL {trend.arrow}"


def test_fr006_demo_trend_ignores_case_and_refuses_others(capsys):
    assert cli.main(["--demo", "--demo-trend", "doubledown"]) == 0
    assert capsys.readouterr().out.splitlines()[1] == "112 mg/dL vv"
    with pytest.raises(SystemExit) as caught:
        cli.main(["--demo", "--demo-trend", "Sideways"])
    assert caught.value.code == 2
    assert "invalid choice: 'Sideways'" in capsys.readouterr().err


def test_fr006_demo_values_all_apply(capsys):
    argv = ["--demo", "--demo-mgdl", "62", "--demo-minutes-ago", "2", "--demo-trend", "SingleDown"]
    assert cli.main(argv) == 1
    assert capsys.readouterr().out == "LOW\n62 mg/dL v\n2 min ago\n"


# --- Ctrl+C never reads as "fresh and in range" ------------------------------------------


class Interrupting:
    def fetch_entries(self, count=12):
        raise KeyboardInterrupt


def test_fr006_ctrl_c_one_shot_exits_130(monkeypatch, capsys):
    source_is(monkeypatch, Interrupting())
    assert cli.main([]) == 130
    assert capsys.readouterr() == ("", "lightkeeper: stopped\n")


@pytest.mark.parametrize("where", ["write", "publish"])
def test_fr006_ctrl_c_one_shot_exits_130_wherever_it_lands(monkeypatch, capsys, tmp_path, where):
    ha = RecordingHA(interrupt=where == "publish")
    monkeypatch.setattr(cli, "home_assistant_from_env", lambda interval, thresholds: ha)
    if where == "write":

        def interrupted(path, payload):
            raise KeyboardInterrupt

        monkeypatch.setattr(cli, "write_json", interrupted)
    assert cli.main(["--demo", "--json", str(tmp_path / "s.json")]) == 130
    assert capsys.readouterr().err == "lightkeeper: stopped\n"
    assert ha.finished is False  # Home Assistant's finish() still ran


def test_fr006_ctrl_c_in_a_watch_fetch_exits_0(monkeypatch, capsys):
    source_is(monkeypatch, Interrupting())
    assert cli.main(["--watch"]) == 0
    assert capsys.readouterr() == ("", "")


@pytest.fixture
def broker():
    b = FakeBroker()
    yield b
    b.close()


def broker_env(monkeypatch, broker):
    monkeypatch.setenv("LK_MQTT_HOST", "127.0.0.1")
    monkeypatch.setenv("LK_MQTT_PORT", str(broker.port))
    monkeypatch.setenv("LK_MQTT_TLS", "false")


OFFLINE = {
    "type": "PUBLISH",
    "topic": "lightkeeper/lightkeeper/availability",
    "payload": b"offline",
    "retain": True,
    "qos": 0,
}


def test_fr006_ctrl_c_watch_exits_0_and_marks_ha_offline(monkeypatch, capsys, broker):
    broker_env(monkeypatch, broker)
    stop_after(monkeypatch, 1)  # Ctrl+C while it sleeps
    assert cli.main(["--demo", "--watch"]) == 0
    packets = broker.wait_for(8)
    assert packets[-2:] == [OFFLINE, {"type": "DISCONNECT"}]
    assert capsys.readouterr().err == ""


class InterruptOnSecondFetch:
    """Serves one fresh reading, then Ctrl+C lands in the middle of the next fetch."""

    def __init__(self):
        self.calls = 0

    def fetch_entries(self, count=12):
        self.calls += 1
        if self.calls > 1:
            raise KeyboardInterrupt
        return [entry(112, minutes_ago=3)]


def test_fr006_ctrl_c_mid_fetch_in_watch_still_marks_ha_offline(monkeypatch, broker):
    freeze(monkeypatch)
    broker_env(monkeypatch, broker)
    source_is(monkeypatch, InterruptOnSecondFetch())
    monkeypatch.setattr(cli, "time", types.SimpleNamespace(sleep=lambda seconds: None))
    assert cli.main(["--watch"]) == 0
    packets = broker.wait_for(8)
    assert packets[-2:] == [OFFLINE, {"type": "DISCONNECT"}]


class InterruptedNotifier:
    """Ctrl+C lands after the publish, as the cycle reports itself alive."""

    def ready(self, status):
        pass

    def alive(self, status):
        raise KeyboardInterrupt

    def stopping(self):
        pass


def test_fr006_ctrl_c_one_shot_after_a_publish_leaves_ha_available(monkeypatch, capsys, broker):
    """A one-shot run stopped after publishing exits 130 and leaves the entities as they are."""
    freeze(monkeypatch)
    broker_env(monkeypatch, broker)
    monkeypatch.setattr(cli, "SystemdNotifier", InterruptedNotifier)
    assert cli.main(["--demo"]) == 130
    packets = broker.wait_for(7)
    assert packets[-1] == {"type": "DISCONNECT"}  # finish() ran
    assert OFFLINE not in packets
    assert capsys.readouterr().err == "lightkeeper: stopped\n"


# --- diagnostics on stderr, the screen unchanged -------------------------------------------


def test_fr006_diagnostic_once_per_kind_and_on_recovery_stdout_unchanged(monkeypatch, capsys):
    freeze(monkeypatch)
    dns = urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))
    nightscout_with(
        monkeypatch,
        scripted(
            OK_BODY,
            http_error(401),
            http_error(401),
            dns,
            dns,
            OK_BODY,
            OK_BODY,
            http_error(500),
        ),
    )
    stop_after(monkeypatch, 8)
    assert cli.main(["--watch"]) == 0
    out, err = capsys.readouterr()
    cycles = [FRESH, FAILING, FAILING, FAILING, FAILING, FRESH, FRESH, FAILING]
    assert out == "".join(cycle + SEPARATOR for cycle in cycles)
    assert err.splitlines() == [
        REFUSED,
        DNS,
        "lightkeeper: Nightscout reachable again",
        "lightkeeper: Nightscout answered HTTP 500, a problem on the site. Open the site in a "
        "browser to check it is running",
    ]


def test_fr006_unreachable_site_shows_no_data_and_one_line_naming_dns(monkeypatch, capsys):
    """NIGHTSCOUT_URL=https://nonexistent.invalid, through the real fetcher."""

    class NoDns:
        def open(self, request, timeout):
            raise urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))

    monkeypatch.setattr(nightscout, "_opener", NoDns())
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://nonexistent.invalid")
    assert cli.main([]) == 1
    out, err = capsys.readouterr()
    assert (
        out
        == "NO DATA\nCheck sensor and phone\nConfirm on primary device\nNightscout unreachable\n"
    )
    assert err == DNS + "\n"


def test_fr006_wrong_token_prints_one_line_saying_it_was_refused(monkeypatch, capsys):
    nightscout_with(monkeypatch, scripted(http_error(401)))
    assert cli.main([]) == 1
    assert capsys.readouterr().err == REFUSED + "\n"


def test_fr006_a_failure_that_is_not_nightscouts_is_reported_too(monkeypatch, capsys):
    source_is(monkeypatch, FakeSource(error=RuntimeError("disk on fire")))
    assert cli.main([]) == 1
    out, err = capsys.readouterr()
    assert out.startswith("NO DATA\n")
    assert err == "lightkeeper: could not read the readings: disk on fire\n"


def test_fr006_unusable_entries_are_reported_once(monkeypatch, capsys):
    """The fetch worked but its answer could not be read at all: still advice, still NO DATA."""
    freeze(monkeypatch)
    source_is(monkeypatch, FakeSource(entries=12345))  # not even a list
    stop_after(monkeypatch, 3)
    assert cli.main(["--watch"]) == 0
    out, err = capsys.readouterr()
    assert out.count("NO DATA\n") == 3
    assert len(err.splitlines()) == 1 and err.startswith("lightkeeper: could not read")


def test_nfr001_diagnostics_never_contain_the_token(monkeypatch, capsys):
    token = "readable-s3cret/t+k"
    quoted = urllib.parse.quote(token, safe="")
    freeze(monkeypatch)
    failures = [
        RuntimeError(f"failed for {token}"),  # not Nightscout's: the CLI redacts it
        urllib.error.URLError(f"refused for {quoted}"),
        http_error(401),
        TimeoutError(f"slow {token}"),
        OSError(f"boom {token!r}"),
    ]

    class Leaky:
        def __init__(self):
            self.client = NightscoutClient(
                "https://ns.example.com", token=token, fetcher=scripted(*failures[1:])
            )
            self.first = True

        def fetch_entries(self, count=12):
            if self.first:
                self.first = False
                raise failures[0]
            return self.client.fetch_entries(count)

    monkeypatch.setenv("NIGHTSCOUT_TOKEN", token)
    source_is(monkeypatch, Leaky())
    stop_after(monkeypatch, len(failures))
    assert cli.main(["--watch"]) == 0
    out, err = capsys.readouterr()
    assert len(err.splitlines()) == 5  # other, unreachable, auth_rejected, timeout, unreachable
    assert "***" in err  # redacted, not dropped
    for text in (out, err):
        assert token not in text
        assert quoted not in text
        assert "s3cret" not in text
    # stdout is only ever the screen: no message text reaches it.
    no_data = (
        "NO DATA\nCheck sensor and phone\nConfirm on primary device\nNightscout unreachable\n"
    )
    assert out == (no_data + SEPARATOR) * len(failures)


# --- stdout is exactly the vector lines, for every vector ------------------------------------


def vector_status(case):
    readings = parse_entries(raw_entries(case))
    custom = case.get("thresholds")
    thresholds = Thresholds() if custom is None else thresholds_of(custom)
    return classify(readings[0] if readings else None, NOW, thresholds), case["error"]


def thresholds_of(custom):
    from datetime import timedelta

    return Thresholds(
        custom["urgent_low"],
        custom["low"],
        custom["high"],
        custom["urgent_high"],
        timedelta(minutes=custom["stale_after_minutes"]),
    )


def use_vector(monkeypatch, case):
    """Serve the vector to the real CLI loop: its entries, its error, its thresholds."""
    freeze(monkeypatch)
    custom = case.get("thresholds")
    if custom:
        for name, key in [
            ("LK_URGENT_LOW", "urgent_low"),
            ("LK_LOW", "low"),
            ("LK_HIGH", "high"),
            ("LK_URGENT_HIGH", "urgent_high"),
            ("LK_STALE_MINUTES", "stale_after_minutes"),
        ]:
            monkeypatch.setenv(name, str(custom[key]))
    error = case["error"]
    source_is(
        monkeypatch, FakeSource(raw_entries(case), NightscoutError(error) if error else None)
    )
    if error:
        # One fetch cannot both fail and return the reading, so the vector's
        # reading stands in for the last good one an earlier cycle kept.
        real = cli.current_status

        def with_last_good(source, now, thresholds, last_good=None):
            readings = parse_entries(raw_entries(case))
            kept = classify(readings[0] if readings else None, now, thresholds)
            return real(source, now, thresholds, kept)

        monkeypatch.setattr(cli, "current_status", with_last_good)


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_fr006_piped_output_is_byte_identical_for_every_vector(
    case, monkeypatch, capsys, tmp_path
):
    """Pipes, cron, systemd and --json read exactly what they always have."""
    use_vector(monkeypatch, case)
    screen = "\n".join(case["lines"]) + "\n"
    target = tmp_path / "status.json"

    assert cli.main(["--json", str(target)]) == (0 if case["level"] == "IN RANGE" else 1)
    assert capsys.readouterr().out == screen
    status, error = vector_status(case)
    text = json.dumps(status_payload(status, error, NOW), indent=2, sort_keys=True) + "\n"
    assert target.read_bytes() == text.replace("\n", os.linesep).encode("utf-8")

    stop_after(monkeypatch, 3)
    assert cli.main(["--watch"]) == 0
    assert capsys.readouterr().out == (screen + SEPARATOR) * 3


# --- the interactive frame ----------------------------------------------------------------


def demo_frame(note=None, color=True, escapes=True, first=False):
    return terminal_view.render_frame(
        FRESH.splitlines(),
        NOW,
        60,
        color=color,
        escapes=escapes,
        columns=80,
        note=note,
        first=first,
    )


def test_fr006_interactive_watch_redraws_the_frame_in_place(monkeypatch):
    freeze(monkeypatch)
    tty = on_a_terminal(monkeypatch)
    stop_after(monkeypatch, 3)
    assert cli.main(["--demo", "--watch"]) == 0
    # Cleared once, then homed and rewritten: the scrollback never grows.
    expected = demo_frame(first=True) + demo_frame() + demo_frame() + terminal_view.RESET
    assert tty.getvalue() == expected
    assert tty.getvalue().count(terminal_view.CLEAR_SCREEN) == 1


@pytest.mark.parametrize(
    ("argv", "environ"), [(["--no-color"], {}), ([], {"NO_COLOR": "1"})], ids=["flag", "env"]
)
def test_fr006_no_color_keeps_the_shape_cues(monkeypatch, argv, environ):
    freeze(monkeypatch)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    tty = on_a_terminal(monkeypatch)
    stop_after(monkeypatch, 1)
    assert cli.main(["--demo", "--demo-mgdl", "62", "--watch", *argv]) == 0
    assert "\x1b[4mLOW" in tty.getvalue()  # the underline, LOW's rule, survives
    assert "\x1b[4;31m" not in tty.getvalue()


def test_fr006_vt_failure_draws_the_plain_frame(monkeypatch):
    freeze(monkeypatch)
    tty = on_a_terminal(monkeypatch, vt=False)
    stop_after(monkeypatch, 2)
    assert cli.main(["--demo", "--watch"]) == 0
    assert tty.getvalue() == demo_frame(escapes=False) * 2
    assert "\x1b" not in tty.getvalue()


@pytest.mark.parametrize(
    ("argv", "environ"),
    [(["--watch"], {"TERM": "dumb"}), ([], {})],
    ids=["term-dumb", "one-shot"],
)
def test_fr006_dumb_terminals_and_one_shots_get_the_plain_lines(monkeypatch, argv, environ):
    freeze(monkeypatch)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    tty = on_a_terminal(monkeypatch)
    stop_after(monkeypatch, 2)
    assert cli.main(["--demo", *argv]) == 0
    expected = (FRESH + SEPARATOR) * 2 if argv else FRESH
    assert tty.getvalue() == expected


def test_fr006_framed_advice_stays_in_view_under_the_footer(monkeypatch, capsys):
    freeze(monkeypatch)
    nightscout_with(monkeypatch, scripted(OK_BODY, http_error(401), http_error(401), OK_BODY))
    tty = on_a_terminal(monkeypatch)
    stop_after(monkeypatch, 4)
    assert cli.main(["--watch"]) == 0
    note = REFUSED.removeprefix("lightkeeper: ")
    failing = terminal_view.render_frame(FAILING.splitlines(), NOW, 60, columns=80, note=note)
    expected = demo_frame(first=True) + failing + failing + demo_frame() + terminal_view.RESET
    assert tty.getvalue() == expected
    # stderr still gets its one line per change.
    assert capsys.readouterr().err.splitlines() == [
        REFUSED,
        "lightkeeper: Nightscout reachable again",
    ]


# --- write failures in plain words -----------------------------------------------------------


def test_fr006_write_error_in_plain_words(capsys, tmp_path):
    missing = tmp_path / "no-such-folder" / "screen.png"
    assert cli.main(["--demo", "--png", str(missing)]) == 2
    err = capsys.readouterr().err
    assert err == f"Could not write {missing}: the folder {missing.parent} does not exist\n"
    assert ".tmp" not in err and "Errno" not in err and "WinError" not in err


def test_fr006_write_error_names_a_folder_in_the_way(capsys, tmp_path):
    folder = tmp_path / "status.json"
    folder.mkdir()
    assert cli.main(["--demo", "--json", str(folder)]) == 2
    assert capsys.readouterr().err == f"Could not write {folder}: {folder} is a folder\n"
    assert list(folder.parent.iterdir()) == [folder]  # no temporary file left behind


def test_fr006_write_error_names_a_file_where_a_folder_should_be(capsys, tmp_path):
    blocker = tmp_path / "notes.txt"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "panel.bmp"
    assert cli.main(["--demo", "--bmp", str(target)]) == 2
    assert (
        capsys.readouterr().err == f"Could not write {target}: {blocker} is a file, not a folder\n"
    )


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            PermissionError(errno.EACCES, "Permission denied", "screen.svg.tmp"),
            "permission denied",
        ),
        (OSError(errno.ENOSPC, "No space left on device"), "the disk is full"),
        (OSError(errno.EROFS, "Read-only file system"), "the disk is read-only"),
        (OSError(errno.EIO, "Input/output error."), "input/output error"),
        (OSError("something odd"), "the write failed"),
    ],
)
def test_fr006_write_errors_are_described_without_errno_or_temp_names(tmp_path, error, reason):
    assert cli.describe_write_error(error, str(tmp_path / "screen.svg")) == reason


def test_fr006_a_bare_file_name_is_written_in_the_current_folder(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    error = PermissionError(errno.EACCES, "Permission denied")
    assert cli.describe_write_error(error, "screen.svg") == "permission denied"


def test_haz011_a_failed_write_removes_its_temporary_file(monkeypatch, tmp_path):
    target = tmp_path / "screen.svg"

    def half_written(temp):
        temp.write_text("<svg", encoding="utf-8")
        raise OSError(errno.ENOSPC, "No space left on device")

    with pytest.raises(OSError) as caught:
        cli._replace(target, half_written)
    assert caught.value.errno == errno.ENOSPC
    assert list(tmp_path.iterdir()) == []  # no screen.svg.tmp left to fill the disk further

    # Even when the clean-up fails too, the write's own error is the one reported.
    def locked(self, missing_ok=False):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(cli.Path, "unlink", locked)
    with pytest.raises(OSError) as caught:
        cli._replace(target, half_written)
    assert caught.value.errno == errno.ENOSPC


# --- --help ----------------------------------------------------------------------------------


def test_fr006_help_lists_exit_codes_and_examples(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    assert text.isascii()
    for expected in [
        "examples:",
        "lightkeeper --demo",
        "lightkeeper --bmp panel.bmp --panel 800x480",
        "exit codes:",
        "  0    fresh and in range",
        "  1    someone should look",
        "  2    configuration error",
        "  130  a one-shot run stopped with Ctrl+C",
        "NIGHTSCOUT_URL",
        "NIGHTSCOUT_TOKEN",
        "LK_STALE_MINUTES",
        "LK_MQTT_HOST",
        "NO_COLOR",
        cli.ENV_VARS_URL,
        "(default 60, minimum 15)",
        "--no-color",
        "--png PATH",
        "--bmp PATH",
        "--panel PROFILE",
        "trmnl (= waveshare_7in5)",
    ]:
        assert expected in text, expected
    assert (
        cli.ENV_VARS_URL == "https://github.com/esanacore/lightkeeper/blob/main/docs/ENV_VARS.md"
    )


# --- stamped panel images (HAZ-014) ------------------------------------------------------------


@pytest.mark.parametrize("panel", [None, "800x480", "kindle"])
def test_haz014_png_and_bmp_written_atomically_with_stamp(monkeypatch, capsys, tmp_path, panel):
    freeze(monkeypatch)
    renames = []
    real_replace = os.replace

    def recording_replace(source, target):
        renames.append((os.path.basename(source), os.path.basename(target)))
        real_replace(source, target)

    monkeypatch.setattr(cli.os, "replace", recording_replace)
    png, bmp = tmp_path / "panel.png", tmp_path / "panel.bmp"
    argv = ["--demo", "--png", str(png), "--bmp", str(bmp)]
    assert cli.main(argv + (["--panel", panel] if panel else [])) == 0

    lines = capsys.readouterr().out.splitlines()
    profile = resolve(panel or "waveshare_2in9")
    size = (profile.width, profile.height)
    stamped = render_bitmap(lines, *size, stamp=stamp_text(NOW))
    assert stamped.ink != render_bitmap(lines, *size).ink  # the stamp is really drawn
    assert decode_png(png.read_bytes()) == (*size, stamped.ink)
    assert decode_bmp(bmp.read_bytes()) == (*size, stamped.ink)
    # Written beside the target and renamed into place: never seen half-written.
    assert renames == [("panel.png.tmp", "panel.png"), ("panel.bmp.tmp", "panel.bmp")]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["panel.bmp", "panel.png"]


def test_haz014_the_stamp_is_the_local_time_of_the_write(monkeypatch, tmp_path):
    freeze(monkeypatch)
    bmp = tmp_path / "out.bmp"
    assert cli.main(["--demo", "--bmp", str(bmp), "--panel", "800x480"]) == 0
    lines = ["IN RANGE", "112 mg/dL ->", "3 min ago"]
    width, height, pixels = decode_bmp(bmp.read_bytes())
    assert (width, height) == (800, 480)
    assert pixels == render_bitmap(lines, 800, 480, stamp=NOW.astimezone().strftime("%H:%M")).ink


def test_haz011_watch_survives_png_write_failure(monkeypatch, capsys, tmp_path):
    stop_after(monkeypatch, 2)
    missing = tmp_path / "gone" / "panel.png"
    assert cli.main(["--demo", "--watch", "--png", str(missing)]) == 0
    out, err = capsys.readouterr()
    assert out.count("IN RANGE") == 2
    assert err.count(f"Could not write {missing}: the folder") == 2

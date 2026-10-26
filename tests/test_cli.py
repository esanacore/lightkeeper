"""FR-006: the CLI runs offline in demo mode and signals attention via exit code."""

import pytest

from lightkeeper import cli


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
    ]:
        monkeypatch.delenv(name, raising=False)


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
def test_nfr002_bad_threshold_env_stops_startup(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(SystemExit):
        cli.thresholds_from_env()


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
    import json

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
    def __init__(self, fail=False):
        self.fail = fail
        self.payloads = []
        self.finished = None

    def publish(self, payload):
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

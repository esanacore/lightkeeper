"""FR-006: the CLI runs offline in demo mode and signals attention via exit code."""

import pytest

from glucose_watch import cli


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ["NIGHTSCOUT_URL", "NIGHTSCOUT_TOKEN", "GW_URGENT_LOW", "GW_LOW", "GW_HIGH",
                 "GW_URGENT_HIGH", "GW_STALE_MINUTES"]:
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

    def boom(url, timeout):
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
    monkeypatch.setenv("GW_LOW", "75")
    monkeypatch.setenv("GW_STALE_MINUTES", "10")
    t = cli.thresholds_from_env()
    assert t.low == 75
    assert t.stale_after.total_seconds() == 600


@pytest.mark.parametrize("name, value", [("GW_LOW", "abc"), ("GW_HIGH", "50")])
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
    with pytest.raises(KeyboardInterrupt):
        cli.main(["--demo", "--watch", "--interval", "1"])
    assert capsys.readouterr().out.count("IN RANGE") == 2

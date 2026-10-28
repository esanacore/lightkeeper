"""NFR-002: every setting is checked at startup, and a bad one is named with its clash.

`lightkeeper.config` reads the environment for the CLI (and the desktop
window). Each unusable value raises ConfigError naming the variable, the
value, and what it clashes with; the CLI turns that into exit 2.
"""

import argparse
import itertools
from datetime import timedelta

import pytest

from lightkeeper import config
from lightkeeper.config import ConfigError
from lightkeeper.domain.status import Thresholds
from lightkeeper.infrastructure.nightscout import NightscoutClient

THRESHOLD_VARS = ["LK_URGENT_LOW", "LK_LOW", "LK_HIGH", "LK_URGENT_HIGH", "LK_STALE_MINUTES"]
MQTT_VARS = [
    "LK_MQTT_HOST",
    "LK_MQTT_PORT",
    "LK_MQTT_TLS",
    "LK_MQTT_USERNAME",
    "LK_MQTT_PASSWORD",
    "LK_MQTT_DISCOVERY_PREFIX",
    "LK_MQTT_NODE_ID",
]
INTEGER_VARS = [*THRESHOLD_VARS, "LK_MQTT_PORT"]
PASSWORD = "mqtt-pw-do-not-print"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ["NIGHTSCOUT_URL", "NIGHTSCOUT_TOKEN", *THRESHOLD_VARS, *MQTT_VARS]:
        monkeypatch.delenv(name, raising=False)


def mqtt_env(monkeypatch, **values):
    """Set LK_MQTT_HOST to a broker plus any LK_MQTT_* values given by suffix."""
    monkeypatch.setenv("LK_MQTT_HOST", values.pop("host", "broker.example.com"))
    for suffix, value in values.items():
        monkeypatch.setenv(f"LK_MQTT_{suffix.upper()}", value)


def demo_args(**values):
    return argparse.Namespace(**{"demo": True, **values})


# --- thresholds -----------------------------------------------------------------


def test_nfr002_thresholds_come_from_every_variable(monkeypatch):
    for name, value in zip(THRESHOLD_VARS, ["60", "80", "160", "220", "10"], strict=True):
        monkeypatch.setenv(name, value)
    assert config.thresholds_from_env() == Thresholds(
        urgent_low=60, low=80, high=160, urgent_high=220, stale_after=timedelta(minutes=10)
    )


def test_nfr002_unset_thresholds_are_the_domain_defaults():
    assert config.thresholds_from_env() == Thresholds()


@pytest.mark.parametrize("name", THRESHOLD_VARS)
@pytest.mark.parametrize("value", ["", "   "])
def test_nfr002_empty_threshold_means_the_default(monkeypatch, name, value):
    """An empty variable is unset, as `.env.example`'s empty LK_MQTT_HOST relies on."""
    monkeypatch.setenv(name, value)
    assert config.thresholds_from_env() == Thresholds()


def test_nfr002_surrounding_spaces_and_a_sign_are_accepted(monkeypatch):
    monkeypatch.setenv("LK_LOW", " 75 ")
    monkeypatch.setenv("LK_STALE_MINUTES", "+12")
    thresholds = config.thresholds_from_env()
    assert (thresholds.low, thresholds.stale_after) == (75, timedelta(minutes=12))


@pytest.mark.parametrize("name", INTEGER_VARS)
@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("abc", "'abc'"),
        ("7.5", "'7.5'"),
        ("70 mg/dL", "'70 mg/dL'"),
        ("1e3", "'1e3'"),
        # int() would take these; a setting should be plain digits.
        ("7_0", "'7_0'"),
        ("٧٠", "'٧٠'"),
    ],
)
def test_nfr002_non_integer_names_the_variable_and_value(monkeypatch, name, value, shown):
    if name == "LK_MQTT_PORT":
        mqtt_env(monkeypatch, port=value)
        build = lambda: config.home_assistant_from_env(60, Thresholds())  # noqa: E731
    else:
        monkeypatch.setenv(name, value)
        build = config.thresholds_from_env
    with pytest.raises(ConfigError) as caught:
        build()
    assert str(caught.value) == f"{name}={shown} must be a whole number"


@pytest.mark.parametrize("name", INTEGER_VARS)
def test_nfr002_far_too_large_numbers_are_refused_not_crashed_on(monkeypatch, name):
    """Thousands of digits would make int() raise, and a huge stale limit overflow timedelta."""
    if name == "LK_MQTT_PORT":
        mqtt_env(monkeypatch, port="9" * 5000)
        build = lambda: config.home_assistant_from_env(60, Thresholds())  # noqa: E731
    else:
        monkeypatch.setenv(name, "9" * 5000)
        build = config.thresholds_from_env
    with pytest.raises(ConfigError) as caught:
        build()
    message = str(caught.value)
    assert message.startswith(f"{name}='999999999999999999999999'...")
    assert message.endswith("is far too large")
    assert len(message) < 100


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"LK_LOW": "200"}, "LK_LOW=200 must be below LK_HIGH=180 (the default)"),
        ({"LK_URGENT_LOW": "75"}, "LK_URGENT_LOW=75 must be below LK_LOW=70 (the default)"),
        ({"LK_HIGH": "260"}, "LK_HIGH=260 must be below LK_URGENT_HIGH=250 (the default)"),
        ({"LK_HIGH": "50"}, "LK_LOW=70 (the default) must be below LK_HIGH=50"),
        (
            {"LK_URGENT_HIGH": "170"},
            "LK_HIGH=180 (the default) must be below LK_URGENT_HIGH=170",
        ),
        ({"LK_LOW": "90", "LK_HIGH": "90"}, "LK_LOW=90 must be below LK_HIGH=90"),
        (
            {"LK_URGENT_LOW": "39"},
            "LK_URGENT_LOW=39 must be at least 40 mg/dL, the lowest a sensor measures",
        ),
        (
            {"LK_URGENT_HIGH": "401"},
            "LK_URGENT_HIGH=401 must be at most 400 mg/dL, the highest a sensor measures",
        ),
        ({"LK_STALE_MINUTES": "0"}, "LK_STALE_MINUTES=0 must be at least 1 minute"),
        ({"LK_STALE_MINUTES": "-5"}, "LK_STALE_MINUTES=-5 must be at least 1 minute"),
    ],
)
def test_nfr002_out_of_order_thresholds_name_the_clash(monkeypatch, env, message):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError) as caught:
        config.thresholds_from_env()
    assert str(caught.value) == message


def test_nfr002_config_error_is_a_value_error():
    assert issubclass(ConfigError, ValueError)


def test_nfr002_config_accepts_exactly_what_the_domain_accepts(monkeypatch):
    """The named checks are the domain's rule, no stricter and no looser.

    If Thresholds ever gains a rule config.py does not check, this fails
    instead of the CLI crashing with a bare ValueError.
    """
    for urgent_low, low, high, urgent_high in itertools.product(
        [39, 40, 70, 180], [40, 70, 71, 180], [70, 180, 250], [180, 250, 400, 401]
    ):
        for stale in (-1, 0, 1, 15):
            values = [urgent_low, low, high, urgent_high, stale]
            for name, value in zip(THRESHOLD_VARS, values, strict=True):
                monkeypatch.setenv(name, str(value))
            try:
                Thresholds(urgent_low, low, high, urgent_high, timedelta(minutes=stale))
                domain_ok = True
            except ValueError:
                domain_ok = False
            try:
                config.thresholds_from_env()
                config_ok = True
            except ConfigError:
                config_ok = False
            assert config_ok == domain_ok, values


# --- Home Assistant over MQTT -----------------------------------------------------


def test_fr008_mqtt_is_off_without_a_host_even_when_other_settings_are_bad(monkeypatch):
    monkeypatch.setenv("LK_MQTT_HOST", "  ")
    monkeypatch.setenv("LK_MQTT_PORT", "abc")
    assert config.home_assistant_from_env(60, Thresholds()) is None


def test_fr008_empty_mqtt_settings_mean_the_defaults(monkeypatch):
    mqtt_env(monkeypatch, port="", tls="", node_id="", discovery_prefix="", username="")
    ha = config.home_assistant_from_env(60, Thresholds())
    assert (ha._mqtt.port, ha._mqtt._tls) == (8883, True)
    assert (ha.node_id, ha.discovery_prefix) == ("lightkeeper", "homeassistant")
    assert ha._mqtt.client_id == "lightkeeper-lightkeeper"
    assert ha._mqtt._username is None and ha._mqtt._password is None


def test_fr008_every_mqtt_setting_reaches_the_publisher(monkeypatch):
    mqtt_env(
        monkeypatch,
        host="localhost",
        port="11883",
        tls="off",
        username="lightkeeper",
        password=PASSWORD,
        node_id="bedside",
        discovery_prefix="ha_test",
    )
    ha = config.home_assistant_from_env(30, Thresholds(stale_after=timedelta(minutes=10)))
    mqtt = ha._mqtt
    assert (mqtt.host, mqtt.port, mqtt._tls) == ("localhost", 11883, False)
    assert (mqtt._username, mqtt._password, mqtt.client_id) == (
        "lightkeeper",
        PASSWORD,
        "lightkeeper-bedside",
    )
    assert (ha.node_id, ha.discovery_prefix, ha.expire_after) == ("bedside", "ha_test", 180)


@pytest.mark.parametrize("value", ["0", "65536", "-1", "100000"])
def test_nfr002_mqtt_port_out_of_range_names_the_value(monkeypatch, value):
    mqtt_env(monkeypatch, port=value, password=PASSWORD, username="u")
    with pytest.raises(ConfigError) as caught:
        config.home_assistant_from_env(60, Thresholds())
    assert str(caught.value) == f"LK_MQTT_PORT={int(value)} must be a port number from 1 to 65535"
    assert PASSWORD not in str(caught.value)


@pytest.mark.parametrize("port", ["1", "1883", "65535"])
def test_fr008_mqtt_port_edges_are_accepted(monkeypatch, port):
    mqtt_env(monkeypatch, port=port)
    assert config.home_assistant_from_env(60, Thresholds())._mqtt.port == int(port)


def test_haz013_mqtt_tls_must_be_true_or_false(monkeypatch):
    mqtt_env(monkeypatch, tls="maybe")
    with pytest.raises(ConfigError, match=r"^LK_MQTT_TLS='maybe' must be true or false$"):
        config.home_assistant_from_env(60, Thresholds())


@pytest.mark.parametrize("value", ["false", "OFF", "0", "No"])
def test_haz013_plain_mqtt_to_a_remote_broker_names_both_settings(monkeypatch, value):
    mqtt_env(monkeypatch, tls=value, password=PASSWORD, username="u")
    with pytest.raises(ConfigError) as caught:
        config.home_assistant_from_env(60, Thresholds())
    message = str(caught.value)
    assert "LK_MQTT_TLS=false" in message and "LK_MQTT_HOST=broker.example.com" in message
    assert "unencrypted" in message and PASSWORD not in message


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST", "127.0.0.1", "::1"])
def test_haz013_plain_mqtt_is_allowed_on_this_machine(monkeypatch, host):
    mqtt_env(monkeypatch, host=host, tls="false")
    assert config.home_assistant_from_env(60, Thresholds())._mqtt.port == 1883


@pytest.mark.parametrize("name", ["LK_MQTT_NODE_ID", "LK_MQTT_DISCOVERY_PREFIX"])
@pytest.mark.parametrize("value", ["bed side", "a/b", "x#", "café"])
def test_haz013_mqtt_ids_with_unsafe_characters_are_named(monkeypatch, name, value):
    mqtt_env(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError) as caught:
        config.home_assistant_from_env(60, Thresholds())
    assert str(caught.value) == (
        f"{name}={value!r} may contain only letters, digits, '_' and '-'"
    )


def test_nfr001_mqtt_password_without_a_user_is_refused_without_printing_it(monkeypatch):
    """MQTT 3.1.1 cannot send a password alone; it used to fail at the first publish."""
    mqtt_env(monkeypatch, password=PASSWORD)
    with pytest.raises(ConfigError) as caught:
        config.home_assistant_from_env(60, Thresholds())
    assert "LK_MQTT_PASSWORD is set but LK_MQTT_USERNAME is not" in str(caught.value)
    assert PASSWORD not in str(caught.value)


# --- the entry source -------------------------------------------------------------


def test_fr006_demo_source_uses_the_defaults_when_values_are_missing():
    for args in (demo_args(), demo_args(demo_mgdl=None, demo_minutes_ago=None, demo_trend=None)):
        source = config.source_from_env(args)
        assert isinstance(source, config.DemoSource)
        (entry,) = source.fetch_entries()
        assert (entry["sgv"], entry["direction"]) == (112, "Flat")


def test_fr006_demo_source_takes_its_values_from_the_arguments():
    args = demo_args(demo_mgdl=62, demo_minutes_ago=0, demo_trend="SingleDown")
    (entry,) = config.source_from_env(args).fetch_entries(count=3)
    assert (entry["type"], entry["sgv"], entry["direction"]) == ("sgv", 62, "SingleDown")


def test_fr006_demo_values_without_demo_never_make_a_demo_source(monkeypatch):
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")
    args = argparse.Namespace(demo=False, demo_mgdl=62, demo_minutes_ago=0, demo_trend="Flat")
    assert isinstance(config.source_from_env(args), NightscoutClient)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_fr006_missing_nightscout_url_is_named(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("NIGHTSCOUT_URL", value)
    with pytest.raises(ConfigError) as caught:
        config.source_from_env(argparse.Namespace(demo=False))
    assert str(caught.value).startswith("NIGHTSCOUT_URL is not set")
    assert "--demo" in str(caught.value)


def test_nfr001_url_and_token_reach_the_client_trimmed(monkeypatch):
    seen = {}

    def factory(url, token=None):
        seen.update(url=url, token=token)
        return "client"

    monkeypatch.setenv("NIGHTSCOUT_URL", "  https://ns.example.com \n")
    monkeypatch.setenv("NIGHTSCOUT_TOKEN", " readable-0123 \n")
    assert config.source_from_env(argparse.Namespace(demo=False), factory) == "client"
    assert seen == {"url": "https://ns.example.com", "token": "readable-0123"}


def test_nfr001_empty_token_means_none(monkeypatch):
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")
    monkeypatch.setenv("NIGHTSCOUT_TOKEN", " ")
    client = config.source_from_env(argparse.Namespace(demo=False))
    assert client._token is None


@pytest.mark.parametrize(
    "url",
    [
        "http://ns.example.com",
        "ftp://ns.example.com",
        "ns.example.com",
        "https://ns.example.com/?token=s3cret-in-url",
        "https://user:s3cret-in-url@ns.example.com",
        "https://ns.example.com:s3cret",
    ],
)
def test_nfr001_unusable_url_is_named_never_echoed(monkeypatch, url):
    monkeypatch.setenv("NIGHTSCOUT_URL", url)
    with pytest.raises(ConfigError) as caught:
        config.source_from_env(argparse.Namespace(demo=False))
    message = str(caught.value)
    assert message.startswith("NIGHTSCOUT_URL ")
    assert "s3cret" not in message and url not in message
    # The library's parameter names mean nothing to a person editing settings.
    assert "allow_http" not in message and "base_url" not in message


def test_nfr001_http_url_is_refused_in_plain_words(monkeypatch):
    monkeypatch.setenv("NIGHTSCOUT_URL", "http://ns.example.com")
    with pytest.raises(ConfigError) as caught:
        config.source_from_env(argparse.Namespace(demo=False))
    assert str(caught.value).startswith("NIGHTSCOUT_URL must use https")


@pytest.mark.parametrize("token", ["s3cret-tok\nen", "s3cret\x1b[2J", "s3cret-café"])
def test_nfr001_unusable_token_is_named_never_echoed(monkeypatch, token):
    monkeypatch.setenv("NIGHTSCOUT_URL", "https://ns.example.com")
    monkeypatch.setenv("NIGHTSCOUT_TOKEN", token)
    with pytest.raises(ConfigError) as caught:
        config.source_from_env(argparse.Namespace(demo=False))
    assert str(caught.value).startswith("NIGHTSCOUT_TOKEN must be printable ASCII")
    assert "s3cret" not in str(caught.value)

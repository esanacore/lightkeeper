"""FR-009, FR-016, NFR-001, NFR-003, NFR-005: the Android app's build holds to the rules.

apps/android is a Gradle project this suite cannot build (that is
.github/workflows/android.yml's job), but its safety-relevant source is text,
so the repository's Full suite checks it on every change, with no Android SDK:

- the manifest asks for INTERNET and nothing else, and no cleartext traffic
  is possible (NFR-001, NFR-003): no notification, alarm, service or widget;
- the colors mirror assets/brand/tokens.json (NFR-005);
- the native library compiles the firmware's own C++ in place, so there is no
  fourth implementation of the rules and no copy to drift (FR-009, FR-016);
- the Gradle wrapper is pinned to 9.5.1 by checksum, and the app ships no
  third-party library;
- the phone's status shapes follow the brand status table.

If a color test fails, change tokens.json first, then mirror it in
res/values/colors.xml and res/values-night/colors.xml; never the other way round.
"""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "apps" / "android"
APP = ANDROID / "app"
MAIN = APP / "src" / "main"
RES = MAIN / "res"
CPP = MAIN / "cpp"
KOTLIN = MAIN / "java" / "com" / "esanacore" / "lightkeeper"
FIRMWARE_LIB = ROOT / "firmware" / "xteink" / "lib"
TOKENS = json.loads((ROOT / "assets" / "brand" / "tokens.json").read_text(encoding="utf-8"))
COLOR = TOKENS["color"]
NS = "{http://schemas.android.com/apk/res/android}"
BUILD_DIRS = {"build", ".gradle", ".cxx", ".kotlin", ".idea"}

# The official Gradle 9.5.1 binary distribution and its wrapper JAR. The JAR
# checksum is the one gradle/actions' wrapper validation lists for 9.5.1.
GRADLE_URL = "https://services.gradle.org/distributions/gradle-9.5.1-bin.zip"
GRADLE_SHA256 = "bafc141b619ad6350fd975fc903156dd5c151998cc8b058e8c1044ab5f7b031f"
WRAPPER_JAR_SHA256 = "497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7"

# Colors drawn from two tokens: (light token, dark token).
PAIRS = {
    "lk_panel_paper": ("paper", "night-paper"),
    "lk_panel_ink": ("ink", "night-ink"),
    "lk_hard_shadow": ("beam-soft", "line"),
}


def project_files(pattern):
    """Every file under apps/android matching `pattern`, build output excluded."""
    return sorted(
        p for p in ANDROID.rglob(pattern) if p.is_file() and not BUILD_DIRS & set(p.parts)
    )


def manifest():
    return ET.parse(MAIN / "AndroidManifest.xml").getroot()


# --- the manifest: INTERNET only, no cleartext, nothing that could alarm --------


def test_nfr001_manifest_asks_for_internet_and_nothing_else():
    permissions = [p.get(f"{NS}name") for p in manifest().iter("uses-permission")]
    assert permissions == ["android.permission.INTERNET"]
    for tag in ("permission", "uses-permission-sdk-23", "uses-feature"):
        assert not list(manifest().iter(tag)), f"unexpected <{tag}>"


def test_nfr003_manifest_has_no_service_receiver_provider_or_widget():
    # No foreground service, no alarm receiver, no widget, no notification
    # listener: Lightkeeper never alarms and runs only while on screen.
    application = manifest().find("application")
    tags = {child.tag for child in application}
    assert tags == {"activity"}
    text = (MAIN / "AndroidManifest.xml").read_text(encoding="utf-8")
    for word in (
        "NOTIFICATION",
        "ALARM",
        "FOREGROUND_SERVICE",
        "VIBRATE",
        "WAKE_LOCK",
        "appwidget",
    ):
        assert word not in text.split("-->")[-1], word


def test_nfr001_cleartext_is_off_and_backup_is_off():
    application = manifest().find("application")
    assert application.get(f"{NS}usesCleartextTraffic") == "false"
    assert application.get(f"{NS}allowBackup") == "false"
    assert application.get(f"{NS}fullBackupContent") == "false"
    assert application.get(f"{NS}networkSecurityConfig") == "@xml/network_security_config"
    assert application.get(f"{NS}dataExtractionRules") == "@xml/data_extraction_rules"

    config = ET.parse(RES / "xml" / "network_security_config.xml").getroot()
    base = config.find("base-config")
    assert base.get("cleartextTrafficPermitted") == "false"
    # Only the system's certificate authorities, never a user-added one, and
    # no domain may turn cleartext back on.
    sources = [c.get("src") for c in config.iter("certificates")]
    assert sources == ["system"]
    assert not list(config.iter("domain-config"))
    assert not list(config.iter("debug-overrides"))


def test_nfr001_nothing_leaves_the_phone_in_a_backup_or_transfer():
    rules = ET.parse(RES / "xml" / "data_extraction_rules.xml").getroot()
    for section in ("cloud-backup", "device-transfer"):
        part = rules.find(section)
        assert not list(part.iter("include")), section
        excluded = {e.get("domain") for e in part.iter("exclude")}
        assert {"root", "file", "database", "sharedpref", "external"} <= excluded, section


def test_nfr001_only_the_launcher_activity_is_exported():
    exported = {a.get(f"{NS}name"): a.get(f"{NS}exported") for a in manifest().iter("activity")}
    assert exported == {".MainActivity": "true", ".SettingsActivity": "false"}


# --- the source: no logging, the token only in its header ------------------------


@pytest.mark.parametrize("path", sorted(KOTLIN.glob("*.kt")), ids=lambda p: p.name)
def test_nfr001_no_app_source_logs(path):
    # The token is never logged because nothing is.
    source = path.read_text(encoding="utf-8")
    for call in ("android.util.Log", "Log.d(", "Log.e(", "Log.i(", "println(", "printStackTrace"):
        assert call not in source, f"{path.name}: {call}"


def test_nfr001_the_token_travels_only_in_the_api_secret_header():
    client = (KOTLIN / "NightscoutClient.kt").read_text(encoding="utf-8")
    assert 'const val TOKEN_HEADER = "api-secret"' in client
    assert "setRequestProperty(TOKEN_HEADER, it)" in client
    assert "instanceFollowRedirects = false" in client
    site = (KOTLIN / "SiteAddress.kt").read_text(encoding="utf-8")
    (entries,) = re.findall(r"fun entriesUrl\(([^)]*)\)", site)
    assert entries == "count: Int", "the entries URL takes no token"


# --- the colors mirror tokens.json ------------------------------------------------


def colors(folder):
    """Return {name: hex} for every <color> in res/<folder>/colors.xml."""
    root = ET.parse(RES / folder / "colors.xml").getroot()
    return {c.get("name"): c.text for c in root.iter("color")}


def expected(theme):
    """Return {name: hex} that tokens.json gives every lk_ color in a theme."""
    out = {"lk_" + key.replace("-", "_"): token[theme] for key, token in COLOR.items()}
    for name, (light_id, dark_id) in PAIRS.items():
        out[name] = COLOR[light_id if theme == "light" else dark_id][theme]
    return out


@pytest.mark.parametrize(("folder", "theme"), [("values", "light"), ("values-night", "dark")])
def test_nfr005_android_colors_equal_tokens_json(folder, theme):
    assert colors(folder) == expected(theme), f"res/{folder}/colors.xml has drifted"


def test_nfr005_android_panel_uses_night_paper_in_dark_mode():
    assert colors("values-night")["lk_panel_paper"] == COLOR["night-paper"]["dark"]
    assert colors("values-night")["lk_panel_ink"] == COLOR["night-ink"]["dark"]
    assert colors("values")["lk_panel_paper"] == COLOR["paper"]["light"]


@pytest.mark.parametrize("path", sorted(KOTLIN.glob("*.kt")), ids=lambda p: p.name)
def test_nfr005_no_app_source_makes_a_color_of_its_own(path):
    source = path.read_text(encoding="utf-8")
    assert not re.findall(r"#[0-9A-Fa-f]{6}\b", source), f"{path.name}: hex color"
    assert not re.findall(r"Color\.(rgb|argb|parseColor|RED|GREEN|BLUE|BLACK|WHITE|GRAY)", source)
    assert not re.findall(r"0x[fF]{2}[0-9A-Fa-f]{6}", source), f"{path.name}: ARGB literal"


def test_nfr005_the_theme_uses_brand_colors_and_no_dynamic_color():
    for folder in ("values", "values-night"):
        themes = (RES / folder / "themes.xml").read_text(encoding="utf-8")
        assert "Theme.Material" in themes and "DeviceDefault" not in themes
        for value in re.findall(r"<item name=\"[^\"]+\">([^<]+)</item>", themes):
            assert value.startswith(("@color/lk_", "@android:color/transparent", "true", "false"))


def theme_item(folder, name):
    """Return the value of `android:<name>` in res/<folder>/themes.xml."""
    themes = (RES / folder / "themes.xml").read_text(encoding="utf-8")
    (value,) = re.findall(rf'<item name="android:{name}">([^<]+)</item>', themes)
    return value


def test_nfr005_the_light_navigation_bar_is_opaque_until_dark_buttons_exist():
    # Android 8.0 (API 26) draws only light navigation buttons: on Fog they
    # would all but vanish, so the light theme's bar is Ink there. From 8.1
    # the bar is transparent with dark buttons; in dark mode light buttons
    # sit on the dark window at every level.
    assert theme_item("values", "navigationBarColor") == "@color/lk_ink"
    assert theme_item("values-v27", "navigationBarColor") == "@android:color/transparent"
    assert theme_item("values-v27", "windowLightNavigationBar") == "true"
    assert theme_item("values-night", "navigationBarColor") == "@android:color/transparent"
    assert theme_item("values-night-v27", "windowLightNavigationBar") == "false"


# --- the native library is the firmware's own C++, compiled in place ----------------


def test_fr009_cmake_compiles_the_firmware_sources_by_path():
    cmake = (CPP / "CMakeLists.txt").read_text(encoding="utf-8")
    (relative,) = re.findall(r'"\$\{CMAKE_CURRENT_SOURCE_DIR\}/([./]+)" ABSOLUTE', cmake)
    assert (CPP / relative).resolve() == ROOT
    assert 'set(LK_FIRMWARE_LIB "${LK_REPO_ROOT}/firmware/xteink/lib")' in cmake
    for library in ("glucose_rules", "nightscout_json", "panel_bitmap"):
        assert f'"${{LK_FIRMWARE_LIB}}/{library}/{library}.cpp"' in cmake, library
        assert (FIRMWARE_LIB / library / f"{library}.cpp").is_file()
    for flag in ("-Wall", "-Wextra", "-Werror", "-Wconversion"):
        assert flag in cmake, flag


def test_fr009_no_copy_of_the_firmware_sources_lives_under_apps_android():
    native = [
        p.relative_to(ANDROID).as_posix()
        for p in project_files("*")
        if p.suffix in {".c", ".cc", ".cpp", ".h", ".hpp", ".inc"}
    ]
    assert native == ["app/src/main/cpp/jni_bridge.cpp"], "the bridge is the only C++ the app owns"
    firmware_names = {p.name for p in FIRMWARE_LIB.rglob("*") if p.is_file()}
    copies = [p for p in project_files("*") if p.name in firmware_names]
    assert not copies, f"copies of firmware files: {copies}"


def test_fr009_the_spec_vectors_are_copied_at_build_time_never_by_hand():
    gradle = (APP / "build.gradle.kts").read_text(encoding="utf-8")
    for name in ("display_vectors.json", "panel_vectors.json", "response_vectors.json"):
        assert f'repoRoot.resolve("spec/{name}")' in gradle, name
    assert not project_files("*_vectors.json"), "a hand copy of a spec file"
    assert 'repoRoot.resolve("assets/brand/png/app-icon.png")' in gradle
    assert not project_files("*.png"), "the icons come from assets/brand at build time"


def test_fr016_the_bridge_draws_with_render_panel_and_shows_nothing_on_refusal():
    bridge = (CPP / "jni_bridge.cpp").read_text(encoding="utf-8")
    assert "lk::render_panel(" in bridge
    assert "lk::newest_reading_from_json(" in bridge
    assert "lk::classify(" in bridge and "lk::render(" in bridge
    # A reading coming back from Kotlin is checked again by the parser's rule.
    assert "lk::parse_entry(raw, &reading)" in bridge
    panel = (KOTLIN / "PanelView.kt").read_text(encoding="utf-8")
    assert "isFilterBitmap = false" in panel
    assert "image = null" in panel and "visibility = GONE" in panel


def test_fr009_the_bridge_follows_the_firmware_clang_format_style():
    ours = (CPP / ".clang-format").read_text(encoding="utf-8")
    firmware = (ROOT / "firmware" / "xteink" / ".clang-format").read_text(encoding="utf-8")

    def settings(text):
        return [line for line in text.splitlines() if line and not line.startswith("#")]

    assert settings(ours) == settings(firmware)


# --- the build: pinned wrapper, pinned toolchain, no shipped library ----------------


def test_nfr004_the_wrapper_pins_gradle_9_5_1_by_checksum():
    properties = (ANDROID / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text(
        encoding="utf-8"
    )
    values = dict(
        line.split("=", 1)
        for line in properties.splitlines()
        if "=" in line and not line.startswith("#")
    )
    assert values["distributionUrl"].replace("\\:", ":") == GRADLE_URL
    assert values["distributionSha256Sum"] == GRADLE_SHA256
    assert values["validateDistributionUrl"] == "true"
    jar = (ANDROID / "gradle" / "wrapper" / "gradle-wrapper.jar").read_bytes()
    assert hashlib.sha256(jar).hexdigest() == WRAPPER_JAR_SHA256
    assert (ANDROID / "gradlew").is_file() and (ANDROID / "gradlew.bat").is_file()
    attributes = (ANDROID / ".gitattributes").read_text(encoding="utf-8")
    assert "gradlew text eol=lf" in attributes and "gradlew.bat text eol=crlf" in attributes


def test_nfr004_the_toolchain_versions_are_pinned():
    root = (ANDROID / "build.gradle.kts").read_text(encoding="utf-8")
    assert 'id("com.android.application") version "9.1.1" apply false' in root
    gradle = (APP / "build.gradle.kts").read_text(encoding="utf-8")
    for line in (
        "compileSdk = 36",
        "minSdk = 26",
        "targetSdk = 36",
        'ndkVersion = "28.2.13676358"',
        'version = "3.22.1"',
    ):
        assert line in gradle, line


def test_nfr003_the_app_ships_no_third_party_library():
    gradle = (APP / "build.gradle.kts").read_text(encoding="utf-8")
    (block,) = re.findall(r"^dependencies \{\n(.*?)^\}", gradle, re.M | re.S)
    declared = re.findall(r'^\s*(\w+)\("([^"]+)"\)', block, re.M)
    assert declared == [
        ("testImplementation", "junit:junit:4.13.2"),
        ("androidTestImplementation", "junit:junit:4.13.2"),
        ("androidTestImplementation", "androidx.test:runner:1.7.0"),
    ]
    # Every line of the block is one of those three (or blank): nothing else ships.
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    assert len(lines) == len(declared)
    assert "compose = true" not in gradle and "fileTree(" not in gradle
    plugins = re.findall(r'^\s*id\("([^"]+)"\)', gradle, re.M)
    assert plugins == ["com.android.application"], "no Kotlin, Compose or other plugin"


# --- the phone's status shapes follow the brand status table -------------------------

BANNER = {
    "plain": "CHIP",
    "rule": "CHIP",
    "inverse": "URGENT",
    "stale": "STALE",
    "dashed": "NO_DATA",
}


def test_nfr005_android_shapes_follow_the_brand_status_table():
    source = (KOTLIN / "Presentation.kt").read_text(encoding="utf-8")
    tones = dict(re.findall(r'^\s+([A-Z_]+)\("([a-z-]+)"\),?$', source, re.M))
    assert tones == {"IN_RANGE": "in-range", "LOW": "low", "HIGH": "high", "STALE": "stale"}
    (stale,) = re.findall(r'const val STALE_HEADLINE = "([^"]+)"', source)
    shapes = {}
    for headline, banner, tone in re.findall(
        r'^\s+("[^"]+"|STALE_HEADLINE) -> Banner\.(\w+) to Tone\.(\w+)$', source, re.M
    ):
        shapes[stale if headline == "STALE_HEADLINE" else headline.strip('"')] = (banner, tone)
    (fallback,) = re.findall(r"^\s+else -> Banner\.(\w+) to Tone\.(\w+)$", source, re.M)
    assert len(shapes) == 6, "one shape per headline that is not NO DATA"
    for name, token in TOKENS["status"].items():
        banner, tone = shapes.get(token["word"], fallback)
        assert banner == BANNER[token["treatment"]], name
        assert tones[tone] == token["color"], name
        assert f"chip-{tones[tone]}" == token["chip"], name
    unknown = TOKENS["unknown_headline"]
    assert fallback[0] == BANNER[unknown["treatment"]]
    assert tones[fallback[1]] == unknown["color"]


# --- CI ------------------------------------------------------------------------------


def test_nfr004_the_android_workflow_pins_its_actions_and_watches_the_right_paths():
    workflow = (ROOT / ".github" / "workflows" / "android.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses:\s*(\S+)", workflow)
    assert uses, "the workflow uses no actions"
    for action in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), (
            f"not pinned by SHA: {action}"
        )
    # Every file the build reads from outside apps/android, the launcher icon included.
    gradle = (APP / "build.gradle.kts").read_text(encoding="utf-8")
    icons = re.findall(r'repoRoot\.resolve\("(assets/brand/png/[^"]+)"\)', gradle)
    assert sorted(icons) == [
        "assets/brand/png/app-icon.png",
        "assets/brand/png/lightkeeper-mark-mono.png",
    ]
    for path in (
        "apps/android/**",
        "firmware/xteink/lib/**",
        "spec/*.json",
        "assets/brand/tokens.json",
        *icons,
        ".github/workflows/android.yml",
    ):
        assert workflow.count(f'"{path}"') == 2, f"{path} in both push and pull_request filters"
    for task in ("assembleDebug", "testDebugUnitTest", "lint", "connectedDebugAndroidTest"):
        assert task in workflow, task
    assert "ndk;28.2.13676358" in workflow and "cmake;3.22.1" in workflow
    assert "permissions:\n  contents: read" in workflow

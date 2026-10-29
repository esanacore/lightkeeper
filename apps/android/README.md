# Lightkeeper for Android

A read-only companion app for Android phones: the same status every Lightkeeper display shows, in the Keeper's Logbook glance, with the bedside panel's own pixels beneath it. It reads Nightscout and nothing else. There is no pump or sensor code here, no alarm, and no widget yet.

There is no fourth copy of the rules. The app compiles the firmware's C++ (`firmware/xteink/lib`: `glucose_rules`, `nightscout_json`, `panel_bitmap`) in place, and reaches it through one small JNI file. Every line on the glance and every pixel of the panel image comes from the same code the bedside device runs, and the instrumented tests run every shared vector through it on the phone.

## Layout

- `app/src/main/cpp/`: `CMakeLists.txt` builds the three firmware libraries by relative path, with the firmware's warning set (`-Wall -Wextra -Werror -Wconversion -Wshadow`), no C++ runtime, and `-Os`. `jni_bridge.cpp` is the only C++ the app owns: it reads a raw Nightscout body (`lk::newest_reading_from_json`), classifies and renders a reading at a given time (`lk::classify`, `lk::render`), and draws the panel image (`lk::render_panel`). A reading coming back from Kotlin is checked again by `lk::parse_entry` before it is classified.
- `app/src/main/java/com/esanacore/lightkeeper/`: framework Views in Kotlin. No AndroidX, no Compose, no third-party library.
  - `NativeRules.kt` is the JNI side; `GlanceModel.kt` keeps the last good reading and re-ages it; `GlanceController.kt` runs the fetch and re-age timers while the screen is visible.
  - `Presentation.kt` arranges one screen of lines (a port of the iOS `ScreenPresentation`); `GlanceView.kt` and `PanelView.kt` draw it.
  - `SiteAddress.kt`, `Settings.kt`, `NightscoutClient.kt` and `TokenStore.kt` are the address check, the thresholds, the one GET, and the sealed token.
- `app/src/test/`: JVM unit tests (no device): the address check case for case with iOS, the threshold rules, the request (header, URL, timeouts, redirect refusal), the captions, the color drift against `assets/brand/tokens.json`, the glance anatomy against every display vector, and the model's bookkeeping.
- `app/src/androidTest/`: instrumented tests on a device or emulator, through JNI: every case in `spec/display_vectors.json` gives exactly its lines, every case in `spec/response_vectors.json` its reading, and every case in `spec/panel_vectors.json` its CRC-32 and ink count (all six profiles, so the 296x128 one the app shows among them); a 40-minute re-age turns STALE with no fetch; the first run shows the setup card and no number; STALE shows no large number; the headline is never under a system bar; and the token is never stored in the clear. A Gradle task copies the spec files into the test assets at build time.

## The glance

Top to bottom, in the Keeper's Logbook order (docs/BRAND.md): the status, the number with its arrow, the age, the context lines, then the chrome. Every word comes from the vector lines.

- **IN RANGE, LOW, HIGH**: the status word in Ink on its tint, in a 2 dp status-color border, 20 sp bold. The number is the hero at 96 sp, with the arrow beside it and the unit under the arrow; only the number (and its arrow, in proportion) shrinks to fit, never below half.
- **URGENT LOW, URGENT HIGH**: a full-width Ink band with the word in Band text and a 4 dp status-color leading rule, at 28 sp bold, never shorter than the number beneath it.
- **STALE - DO NOT TRUST**: a full-width Ink band at 28 sp bold with a hatch in the margin, the largest text on the screen. No big number, no separate arrow, no unit: the `last:` line is shown verbatim at body size, struck through, in Muted (HAZ-001, HAZ-008).
- **NO DATA**, and any headline nobody planned for: a dashed frame at 28 sp bold and `--` where a number would be.
- The age line is Ink, bold, monospaced. Below the glance, `checked HH:MM` (or `checking Nightscout...` before the first answer) and, during an outage, `Nightscout unreachable since HH:MM`: absolute local times, so nothing on screen ticks.
- Below that, the real 1-bit panel image for the same lines at the waveshare_2in9 size (296x128), stamped with the local time it was drawn, scaled by a whole number with filtering off. Paper and Ink by day, Night paper and Night ink in dark mode. If the rasterizer refuses, no image is shown, never the previous one.
- For TalkBack the status area is one element, read as the display lines in order. (The spoken sentences of `spec/spoken_vectors.json` are Python and Swift only so far.)
- Until a usable address is saved, the glance is replaced by a card, "Add your Nightscout site to start", with no number and no level word, and the app makes no fetch.

The app fetches when the screen appears and every 60 seconds while it is visible, and re-ages the last good reading every 30 seconds and the moment the screen comes back, with no fetch, so the screen turns STALE on time even when fetches stop or the phone has slept. Nothing runs while the screen is hidden.

## Settings

- The address is checked as it is typed, with the iOS app's rule and the same plain-words reasons: https only, just the site (no path, query, fragment or login), a well-formed site name. Save is disabled while it cannot be used.
- The thresholds step by 5 mg/dL (urgent low 40 to 100, low 45 to 150, high 100 to 350, urgent high 105 to 400), Stale after by 1 minute (6 to 60), with the iOS caution above 15 minutes. An impossible set cannot be saved, and one found on disk is reset (HAZ-006).
- The token is sealed with AES-256-GCM under a key in the Android Keystore. Only the sealed bytes sit in the app's private storage, backup is off, and the token field is never offered to an autofill service. It travels only in the `api-secret` header, never in an address (ADR-0009). Use a token with the readable role, never the API secret.

## The safety boundary

- Read-only. One permission, `INTERNET`. One request: a GET of `/api/v1/entries/sgv.json?count=12`, with 10-second timeouts, a 1 MB cap, and no redirects: any redirect is a failed fetch, so the token is never carried anywhere else. Cleartext traffic is off for the whole app, and only the system's certificate authorities are trusted.
- No notifications, alarms, exact alarms, foreground services, widgets, sounds or vibration. Lightkeeper never alarms; the primary CGM app's alarms are the ones to rely on.
- Nothing logs. No error message carries the token or the address.
- Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app.

## Build and install

Supported platforms: Windows, macOS and Linux, with JDK 17 or 21 and the Android SDK (platform 36, NDK 28.2.13676358, CMake 3.22.1). Point Gradle at the SDK with `ANDROID_HOME` or a `local.properties` file (`sdk.dir=...`, not committed). The Gradle wrapper fetches Gradle 9.5.1 and checks it against the pinned checksum.

<details>
<summary>Windows (PowerShell)</summary>

```powershell
cd apps\android
.\gradlew.bat assembleDebug testDebugUnitTest lint
adb install -r app\build\outputs\apk\debug\app-debug.apk
.\gradlew.bat connectedDebugAndroidTest
```

</details>

<details>
<summary>macOS and Linux</summary>

```bash
cd apps/android
./gradlew assembleDebug testDebugUnitTest lint
adb install -r app/build/outputs/apk/debug/app-debug.apk
./gradlew connectedDebugAndroidTest
```

</details>

The debug APK is about 1 MB. To sideload it onto a phone, turn on USB debugging in Developer options and install it with `adb` as above, or copy the APK to the phone and open it (Android asks once to allow installs from that app). `connectedDebugAndroidTest` needs a phone or an emulator attached.

Lint runs with every check on and fails on any error; the checks turned off in `app/lint.xml` each say why. `.github/workflows/android.yml` builds the APK, runs the unit tests and lint, then the instrumented tests on an API 36 emulator, whenever the app, the firmware libraries, the spec vectors or the brand tokens change.

## What it does not do

- No widget, no complication, no background refresh: the screen is current only while it is open. A widget needs the exact-alarm decision first (L-07).
- No connection check button in Settings yet; a failed fetch shows as `Nightscout unreachable` on the glance and the panel.
- No spoken sentences for TalkBack yet, no mmol/L, no delta.
- No release signing or store listing: this slice ships as a sideloaded debug APK.

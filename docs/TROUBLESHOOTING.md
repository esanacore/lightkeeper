# Troubleshooting

Known issues and fixes. If a display ever shows something that disagrees with the primary CGM app, trust the primary app first, then debug.

## Common Issues

### The display says STALE - DO NOT TRUST

- **Symptom**: The first line is STALE and the age keeps growing.
- **Cause**: Nightscout has not received a reading in more than 15 minutes (or `LK_STALE_MINUTES`). Usually the phone lost Bluetooth to the sensor, Trio is not running in the background, the phone is offline, or the sensor is warming up.
- **Solution**: Check the Dexcom G7 app and Trio on the primary phone first, then the Nightscout site in a browser. The display is doing its job; it recovers on its own when fresh data arrives.

### The display says "time is in the future"

- **Symptom**: STALE with "time is in the future".
- **Cause**: A clock is wrong on the phone, the Nightscout server, or the display device.
- **Solution**: Turn on automatic network time on every device. On a Raspberry Pi, check `timedatectl`.

### NO DATA with "Nightscout unreachable"

- **Symptom**: The program can't reach Nightscout at all and has no earlier reading.
- **Cause**: Wrong `NIGHTSCOUT_URL`, DNS or network failure, the site is down, or the token is wrong or lacks the `readable` role.
- **Solution**: Read the `lightkeeper:` line on stderr (the next section): it names which of these it is. Open the URL in a browser from the same device. Re-create the token in Nightscout's admin tools if needed. Error messages never print the token, so it is safe to share them.

### A `lightkeeper:` line on stderr

- **Symptom**: The screen says "Nightscout unreachable" (under NO DATA, or under an aging reading that turns STALE), and stderr, `journalctl -u lightkeeper`, or the note under the `--watch` frame has one line starting `lightkeeper:`.
- **Cause**: The line names the link that failed. It is written once when the failure starts or changes, not every refresh. The screen text stays "Nightscout unreachable" whatever failed, because the screen's job is only to say the data cannot be trusted.
- **Solution**: Find the line below and check what it says. The token never appears in these lines.

| The line starts with | What failed | What to check |
| :--- | :--- | :--- |
| `Nightscout refused the token (HTTP 401)` or `(HTTP 403)` | Nightscout answered, but not to this token | `NIGHTSCOUT_TOKEN` is a token with the `readable` role, copied whole, never the API secret. Re-create it in Nightscout's admin tools if unsure. |
| `Nightscout needs a token (HTTP 401)` | The site refuses readers without a token (`AUTH_DEFAULT_ROLES=denied`) | Set `NIGHTSCOUT_TOKEN` to a `readable` token. |
| `Nightscout answered HTTP 404 (not found)` | The address reaches a web server, but not Nightscout's API | `NIGHTSCOUT_URL` is the address you open Nightscout at in a browser, with no extra path. |
| `Nightscout answered HTTP 500` (or another 5xx), `a problem on the site` | Nightscout itself is failing | Open the site in a browser; check its hosting (database, app logs). The display recovers on its own. |
| `Nightscout answered HTTP` followed by another code | Something between, or an unusual answer | `NIGHTSCOUT_URL`; any proxy or firewall in front of the site. |
| `Could not find Nightscout's address (the DNS lookup failed)` | The name in `NIGHTSCOUT_URL` does not resolve | The spelling of `NIGHTSCOUT_URL`, and that this device is online (`ping` the name). |
| `Could not connect to Nightscout` | No connection: refused, reset, or no route | `NIGHTSCOUT_URL`, that the site is up, and this device's network. |
| `Nightscout did not answer within 10 seconds` | The site or the network is too slow | That the site is up and this device is online. A free-tier host that sleeps may answer on the next refresh. |
| `The secure (TLS) connection to Nightscout failed` | The certificate, or the TLS handshake | `NIGHTSCOUT_URL` is the site's real `https` address, and this device's clock is right (`timedatectl` on a Pi): a wrong clock makes valid certificates look expired. |
| `Nightscout answered, but not with a list of readings` | The answer was not Nightscout's entries: a login, maintenance or captive-portal page, or something cut off | `NIGHTSCOUT_URL` points at Nightscout itself; open it in a browser from this device. |
| `Nightscout redirected to a different address` | The site sent the request to another scheme or host, which is refused so the token never leaves the site | Set `NIGHTSCOUT_URL` to the final `https` address the browser ends up at. |
| `could not read the readings:` | Anything else, with its message | Report it with the message; the token is redacted as `***`. |
| `Nightscout reachable again` | Nothing now: the failure has cleared | Nothing. |
| `stopped` | A one-shot run was stopped with Ctrl+C, and exited 130 | Nothing; run it again. |

### "Could not write" on stderr

- **Symptom**: `Could not write <path>: <reason>` once per refresh with `--svg`, `--json`, `--png` or `--bmp`. A one-shot run exits 2; `--watch` keeps the display going and retries each refresh (HAZ-011).
- **Cause**: The reason says it in plain words: `the folder ... does not exist`, `... is a file, not a folder`, `... is a folder`, `permission denied`, `the disk is full`, or `the disk is read-only`.
- **Solution**: Create the folder, or point the option at a file in one the service may write (`/run/lightkeeper/` under the systemd unit). A failed write, or one cut short by Ctrl+C, leaves no temporary file behind.

### Configuration error on startup

- **Symptom**: Exit code 2 and one line, `Configuration error: ...`, naming the variable, its value, and what it clashes with, for example `LK_LOW=200 must be below LK_HIGH=180 (the default)`. Nothing is shown first.
- **Cause**: A setting that cannot be used: an `http://` or malformed `NIGHTSCOUT_URL`, a token with a line break or a non-ASCII character, a threshold that is not a whole number or is out of order, `LK_STALE_MINUTES` below 1, `LK_MQTT_PORT` outside 1 to 65535, `LK_MQTT_TLS` that is not true or false, plain MQTT to a broker that is not on localhost, `LK_MQTT_PASSWORD` without `LK_MQTT_USERNAME`, or an `LK_MQTT_NODE_ID` or `LK_MQTT_DISCOVERY_PREFIX` with characters other than letters, digits, `_`, and `-`.
- **Solution**: Fix the setting the message names, against `docs/ENV_VARS.md`. Use the HTTPS URL; turn TLS on for a remote broker. A `--demo-*` option without `--demo`, or a `--panel` too small for every screen, also exits 2, with `lightkeeper: error:` and the usage line.

### "Home Assistant publish failed" in the log

- **Symptom**: The display keeps working, and each cycle logs "Home Assistant publish failed: ...".
- **Cause**: The broker is unreachable, refuses the user or password, or does not trust the TLS setup. The password never appears in the message.
- **Solution**: Check `LK_MQTT_HOST`, `LK_MQTT_PORT` (8883 with TLS), the broker user, and its ACL. Lightkeeper reconnects on the next cycle by itself.

### Home Assistant shows the Lightkeeper sensors as unavailable

- **Symptom**: The four sensors read `unavailable`.
- **Cause**: The designed behavior when the publisher stops (HAZ-013): the broker published the Last Will, or no update arrived within `expire_after` (three refresh intervals, capped at the stale limit), or the service was stopped cleanly.
- **Solution**: Check the display device: `systemctl status lightkeeper` and `journalctl -u lightkeeper -f`. The sensors return on the next successful publish.

### Firmware host tests on Windows without WSL

- **Symptom**: `make -C firmware/xteink test` cannot link AddressSanitizer with a MinGW toolchain.
- **Cause**: MinGW toolchains (MSYS2, WinLibs, Git Bash) cannot link the sanitizers.
- **Solution**: Run it in WSL (`wsl -- make -C firmware/xteink test`), or with Windows clang++ for the MSVC target (as shipped with the Swift toolchain): `mingw32-make -C firmware/xteink test CXX=clang++ BUILD=build/asan CXXFLAGS="-std=c++17 -Wall -Wextra -Werror -Wconversion -Wshadow -g -fsanitize=address,undefined -fno-sanitize-recover=all -D_CRT_SECURE_NO_WARNINGS -Ilib/glucose_rules -Ilib/nightscout_json -Ilib/panel_bitmap -Ibuild/asan"`, with the folder holding clang's x86_64 `clang_rt.asan_dynamic.dll` on `PATH`. The Makefile calls `python3`; if there is none on `PATH`, add `PYTHON=python`. CI's Linux run is the authority.

### The demo's panel tests skip or fail

- **Symptom**: `tests/test_demo_panel.py` skips its Node tests locally, or fails them on CI, or asks you to run `tools/gen_demo_panel.py`.
- **Cause**: `node` is missing (Node 20 or later is needed), or `demo.html` was edited after its generated block was written; the page counts its own size.
- **Solution**: Install Node 20 or later. After any edit to `demo.html` (including a states block rewritten by `gen_display_gallery.py`), run `python tools/gen_demo_panel.py`.

### The desktop window says it needs Tk

- **Symptom**: `python -m lightkeeper.desktop` exits 2 with `lightkeeper: the window needs Tk, which this Python does not have: install python3-tk (for example, sudo apt install python3-tk) or a Python that includes Tk`.
- **Cause**: This Python has no tkinter. The python.org installers for Windows and macOS include it; Debian, Ubuntu and Raspberry Pi OS ship it separately, and Homebrew's `python@3.12` needs `python-tk@3.12`.
- **Solution**: `sudo apt install python3-tk`, `brew install python-tk@3.12`, or reinstall from python.org with Tcl/Tk ticked. The CLI never needs Tk.

### The desktop window says it could not open the window

- **Symptom**: Exit 2 with `lightkeeper: could not open the window: ...` and Tk's reason.
- **Cause**: There is no display to open a window on: an SSH session, a headless Pi, or a service.
- **Solution**: Run it in a desktop session. On a headless device, use the CLI's `--png` or `--svg` instead.

### The desktop window is smaller than --scale asked for

- **Symptom**: One line on stderr such as `lightkeeper: at --scale 2 the trmnl panel is larger than this screen, so each panel pixel is drawn as 3x3 screen pixels instead of 4x4` (the numbers vary).
- **Cause**: By design. The window always fits the screen at the largest whole zoom that does, so the age, the stamp and `Nightscout unreachable` are never off screen. A panel that does not fit even at one screen pixel a panel pixel exits 2 with `Configuration error: a WxH panel does not fit on this WxH screen even at one screen pixel a panel pixel: choose a smaller panel`, with the sizes filled in.
- **Solution**: Nothing, or choose a smaller `--panel`.

### `lightkeeper-window` opens nothing

- **Symptom**: On Windows, the installed `lightkeeper-window` launcher starts and no window appears.
- **Cause**: The launcher has no console, so a configuration error, such as `NIGHTSCOUT_URL` not set, has nowhere to go; it exits 2 without a word.
- **Solution**: Run `python -m lightkeeper.desktop` in a terminal to read the message, then set the variables for your user (`docs/ENV_VARS.md`).

### The desktop window says Nightscout unreachable and nothing more

- **Symptom**: The window shows `Nightscout unreachable` and stderr says nothing about why.
- **Cause**: The window does not print the CLI's diagnostic lines.
- **Solution**: Run `python -m lightkeeper` once in the same environment and read its `lightkeeper:` line (the table above).

### The Android native build fails on Windows with `ninja: error: mkdir(...)`

- **Symptom**: `gradlew.bat assembleDebug` stops in the native build with `ninja: error: mkdir(CMakeFiles/lightkeeper.dir/...): No such file or directory`, after a `CMAKE_OBJECT_PATH_MAX` warning.
- **Cause**: The checkout path is too long: CMake names the firmware sources' object files after the whole path, and they pass the Windows path limit.
- **Solution**: Keep the checkout path to about 60 characters or fewer, such as `C:\src\lightkeeper`. A 57-character path builds; a 120-character one fails (`apps/android/README.md`, Build and install).

### `connectedDebugAndroidTest` cannot run offline

- **Symptom**: `./gradlew --offline connectedDebugAndroidTest` cannot resolve its test platform.
- **Cause**: AGP's test platform artifacts (`com.android.tools.utp` 32.1.1) are not in the offline Gradle cache.
- **Solution**: Run it online. Offline, build `assembleDebug assembleDebugAndroidTest`, then `adb install -r` both `app/build/outputs/apk/debug/app-debug.apk` and `app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk`, and run `adb shell am instrument -w -r com.esanacore.lightkeeper.test/androidx.test.runner.AndroidJUnitRunner`.

### `testThePanelIsDrawnAtAWholeNumberScale` fails on an emulator

- **Symptom**: One instrumented test fails, with the panel drawn at scale 0; the other 38 pass.
- **Cause**: The emulator's screen is narrower than the 296 px panel plus its frame and the glance's margins, so the panel rightly draws nothing rather than a crop. The default emulator is 320 px wide.
- **Solution**: Use a phone-sized emulator profile, as `android.yml` does with `profile: pixel_6`.

### The Android app shows Nightscout unreachable and says nothing more

- **Symptom**: The glance shows `Nightscout unreachable` with no reason.
- **Cause**: There is no Check connection yet. A refused token, a site that needs a token, a wrong address and no network all show as unreachable.
- **Solution**: Open the site in a browser on the phone, and check the token with the CLI on a computer (`python -m lightkeeper` prints the `lightkeeper:` line above).

## Environment Reset

```bash
deactivate 2>/dev/null; rm -rf .venv
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git submodule update --init --recursive
```

On Windows, remove `.venv` with `Remove-Item -Recurse -Force .venv` and activate with `.\.venv\Scripts\Activate.ps1`.

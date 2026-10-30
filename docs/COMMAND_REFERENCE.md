# Command Reference

Common commands for this repository. Commands are the same on every platform once the virtual environment is active (`docs/SETUP.md`).

## Development

- `python tools/doctor.py`: check every prerequisite and name what's missing.
- `pip install -e ".[dev]"`: install the package in editable mode with test tools.
- `python -m lightkeeper --help`: every option, with examples, the exit codes and the main environment variables.
- `python -m lightkeeper --demo`: run with canned data, no network.
- `python -m lightkeeper --demo --demo-mgdl 62 --demo-minutes-ago 2 --demo-trend SingleDown`: try a specific simulated reading. `--demo-trend` takes a Nightscout trend name (`DoubleUp`, `SingleUp`, `FortyFiveUp`, `Flat`, `FortyFiveDown`, `SingleDown`, `DoubleDown`, `Unknown`) in any case. The `--demo-*` options without `--demo` exit 2, so canned data never appears unless `--demo` is given.
- `python -m lightkeeper`: read once from Nightscout (needs `NIGHTSCOUT_URL`) and print the screen. Exit codes:
  - `0`: fresh and in range.
  - `1`: someone should look (low, high, STALE, NO DATA, or Nightscout unreachable).
  - `2`: a configuration error (the message names the setting and the clash), an unusable option, or a file a one-shot run could not write.
  - `130`: a one-shot run stopped with Ctrl+C, so cron or Home Assistant never read an interrupted run as fresh and in range. `--watch` stopped with Ctrl+C (or by systemd) exits 0.
- `python -m lightkeeper --watch --interval 60`: refresh until Ctrl+C (default 60 seconds, minimum 15). In an interactive terminal the screen redraws in place inside an ASCII logbook frame (`o))) lightkeeper   checked HH:MM:SS`); piped, under systemd, or with `TERM=dumb` the output is exactly the screen lines, with a line of 24 dashes between refreshes.
- `python -m lightkeeper --watch --no-color`: the frame without color; reverse video, underline and strike stay (as `NO_COLOR=1` does).
- `python -m lightkeeper --svg screen.svg --json status.json`: also write the screen as an SVG image and the status as JSON, each replaced atomically. To show the image on a web page, embed the file with `<img>` or `<object>`. If you inline the SVG markup instead, a STALE image defines a hatch pattern with a page-wide id, so inline only one, or draw each with its own `id_prefix` (`render_svg(..., id_prefix=...)` in Python; the CLI has no flag for it).
- `python -m lightkeeper --png panel.png --bmp panel.bmp --panel 800x480`: also write the real 1-bit panel pixels as a PNG and a BMP, each replaced atomically and stamped with the local `HH:MM` they were drawn at. `--panel` takes a profile (`waveshare_2in9`, the default, `waveshare_1in54`, `waveshare_2in13`, `waveshare_4in2`, `waveshare_7in5` or `trmnl`, `kindle`) or a size `WxH`; a size too small for every screen exits 2.
- `python -m lightkeeper.desktop --demo`: a desktop window showing the real panel pixels (FR-018), at a whole-number zoom (`--scale 2`, the default, or `3`, in 96 dpi pixels, so at 200% display scaling `--scale 2` draws each panel pixel as 4x4 device pixels), stamped with the local `HH:MM` of each redraw, for `--panel PROFILE` (as for `--png`; default `waveshare_2in9`). If the window would not fit the screen, the zoom drops to the largest whole number that fits, and one line on stderr says so. `--on-top` keeps it above other windows; `--theme auto|light|dark` (auto, the default, follows the Windows app theme, read once at startup, and is light elsewhere; dark draws the panel in Night paper and Night ink). Keys: `r` check now, `t` pixels or the lines as text, `q` quit. The window re-ages on its own every 30 seconds or sooner and goes STALE on time with no fetch; it fetches every 60 seconds (there is no `--interval`). Exit codes: `0` closed, `2` a setting or option that cannot be used, a panel too large for the screen even at one screen pixel a panel pixel, no tkinter (install `python3-tk` on Linux) or no display, `130` Ctrl+C. Settings are the CLI's environment variables. `lightkeeper-window`, installed by `pip install`, opens the same window with no console window on Windows (D12, pending Eric's review); with no console a configuration error is not shown, so check one with `python -m lightkeeper.desktop` in a terminal.
- When Nightscout fails, stdout still shows only the screen (the last good reading, STALE once it ages, or NO DATA, each with "Nightscout unreachable"), and stderr gets one line naming what failed and what to check, once per change of what failed, then `lightkeeper: Nightscout reachable again` when it recovers. The token is never in it. `docs/TROUBLESHOOTING.md` lists every line.
- With `LK_MQTT_HOST` (and the other `LK_MQTT_*` settings in `docs/ENV_VARS.md`) set, every refresh is also published to Home Assistant over MQTT discovery.

## Testing

- `python -m pytest --cov`: full suite with the 100% coverage floor.
- `python -m pytest --cov --cov-report=term-missing`: show uncovered lines.
- `python -m pytest -k fr003`: everything verifying one requirement.
- `python -m pytest -k fr018`: the desktop window's FR-018 tests (its hung-fetch tests are `-k haz002`, and its brand-token tests `python -m pytest tests/test_tk_window.py tests/test_ppm.py -k nfr005`); `-k "fr018 and not real_tk"` leaves out the three that open a real Tk window (they skip themselves with no display).
- `cd apps/android && ./gradlew assembleDebug testDebugUnitTest lint` (Windows: `.\gradlew.bat assembleDebug testDebugUnitTest lint`): build the Android debug APK and run its 82 JVM unit tests and lint; `./gradlew connectedDebugAndroidTest` runs its 39 instrumented tests on an attached phone or emulator with a phone-sized screen (JDK 17 or 21, Android SDK platform 36, NDK 28.2.13676358, CMake 3.22.1; on Windows a checkout path of about 60 characters or fewer).
- `python -m pytest tests/test_android.py`: the 55 Python checks on the Android app (manifest, cleartext, colors, CMake, wrapper, workflow).
- `make -C firmware/xteink test`: firmware host tests under AddressSanitizer and UBSan.
- `make -C firmware/xteink coverage`: firmware line and branch coverage with gcov (Linux or WSL).
- `python tools/gen_display_gallery.py`: regenerate `docs/DISPLAY_STATES.md`, its images, and the demo's state table after changing `spec/display_vectors.json`; then run `python tools/gen_demo_panel.py`, because the demo page counts its own size.
- `node --test web/panel/panel.test.mjs`: the demo's panel port against all 237 pixel vectors (Node 20 or later; the pytest suite runs it too).
- `python tools/gen_panel_spec.py` (`--check` to report drift): regenerate `spec/panel_vectors.json` and `spec/font5x8.json` after a panel layout or font change, then `make -C firmware/xteink font-header`.
- `python tools/gen_spoken_vectors.py` (`--check` reports drift, `--table` prints the wording review table): regenerate `spec/spoken_vectors.json` after changing `spec/display_vectors.json` or the spoken form.
- `python tools/gen_demo_panel.py` (`--check`): rewrite the demo's generated panel block after any edit to `demo.html`.
- `python tools/gen_brand_pixels.py`: render `assets/brand/pixel-icons.json` to `assets/brand/png/pixel-*.png`.

## Linting & Formatting

- `python -m ruff check .` and `python -m ruff format .`: lint and format Python.
- `python -m mypy`: strict type checking of `src/`.
- `make -C firmware/xteink format-check`: confirm the C++ matches `.clang-format`.
- `pre-commit install && pre-commit install --hook-type pre-push` once, then `pre-commit run --all-files`: all of the above plus whitespace, YAML/JSON syntax, merge markers, large files, private-key detection, and the secrets sweep before push.

## Operations

- `bash constitution/scripts/check_compliance.sh --product .`: constitution document check.
- `bash constitution/scripts/run_declared_tests.sh .`: run the suite exactly as CI does.
- `bash constitution/scripts/check_secrets.sh .`: scan for committed secrets.
- `systemctl status lightkeeper` and `journalctl -u lightkeeper -f`: on a Pi running `deploy/lightkeeper.service`, the current level and the live log.
- `systemd-analyze security lightkeeper`: check the service's sandboxing (expect about 1.2, "OK").
- `cd firmware/xteink && pio run -e bench_s3 -e x4`: build the ESP32 device skeleton for both boards (PlatformIO 6.2.0; nothing is flashed).
- `cd firmware/xteink && pio run -e bench_s3 -t upload`, then `pio device monitor -e bench_s3`: flash the bench board and read its NO DATA panel dump; check the board's flash size first (`firmware/xteink/README.md`).
- `adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`: sideload the Android debug APK onto a phone with USB debugging on (`apps/android/README.md`, Build and install).
- `git submodule update --remote constitution`: pull the latest constitution, then follow `constitution/INTEGRATION.md`.

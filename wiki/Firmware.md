# Firmware

The firmware is the pocket-display port of Lightkeeper: the same safety rules running on an Xteink X4 or X3 e-ink reader, built around an ESP32-C3 with Wi-Fi and Bluetooth. It reads Nightscout over Wi-Fi with the readable token and never talks to the sensor or the pump (ADR-0004). The source is `firmware/xteink/` in the repository, with its own README; the decision behind it is ADR-0006, summarized in [[Architecture Decisions]].

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Why an Xteink, and why C++

The goal is a small dedicated e-ink display that fits in a pocket. The Xteink X4 and X3 use an ESP32-C3, and an open source community firmware (CrossPoint) already exists for them, so custom firmware is realistic. A Raspberry Pi with an e-paper HAT runs the Python code unchanged but is not pocketable; it remains the plan for the bedside display. MicroPython was rejected as harder to verify than C++ with host tests. The device only works where it has Wi-Fi, which limits it to a convenience display, the role ADR-0004 allows.

## What exists today

`firmware/xteink/lib/glucose_rules/` holds `glucose_rules.h` and `glucose_rules.cpp`: the parse, classify, and render rules ported from `src/lightkeeper/domain/` to dependency-free C++17. No heap, no Arduino, fixed-size buffers (four lines of 32 characters including the terminator), and strings that are truncated rather than overflowed. The constants mirror the Python: sentinels at 39 and 401, a 2-minute future skew allowance, a 4-line limit, timestamps bounded to 2000 to 2100, and NaN rejected before any cast. Function names mirror the Python too (`parse_entry`, `classify`, `render`, `Level::Stale`; `newest_reading` is `parse_entries(...)[0]`), per ADR-0007, so the two can be reviewed side by side.

`lib/nightscout_json/` is the device's reader for the raw Nightscout response: a strict, streaming JSON parser with no heap and a nesting limit that reads only `type`, `sgv`, `date`, and `direction`, hands each entry to `parse_entry`, and keeps the newest survivor. `spec/response_vectors.json` holds the raw bodies it must agree with Python and Swift on.

`lib/panel_bitmap/` is the panel rasterizer: an integer-only, heap-free port of the Python panel layout that draws every case in `spec/panel_vectors.json` pixel for pixel (CRC-32 and ink count), with the Keeper 5x8 font compiled in from `spec/font5x8.json` (`firmware/xteink/tools/gen_font_header.py`; `tests/test_firmware_font.py` fails while the header drifts). `make coverage` reports 100% of its lines. What it cannot draw exactly as Python would (a refused size, a bad stamp, a byte outside ASCII, a short buffer) it refuses, leaving the caller's buffer untouched.

`src/` and `platformio.ini` are a build-only device skeleton for the bench ESP32-S3 (`bench_s3`) and the X4 (`x4`): with no Wi-Fi and no clock it renders the NO DATA screen, prints it over USB serial as `#`/`.` rows with its CRC-32, and deep sleeps 60 seconds. The screen and the dump are plain C++ that the host tests read back to the pinned pixels; `src/main.cpp` is the only file that includes Arduino. Every pin stays unset until checked against the schematics. Both boards build offline with zero warnings; `.github/workflows/firmware-device.yml` repeats that build in CI (not run yet).

`firmware/xteink/test/host/test_glucose_rules.cpp` is the host test for the rules; `test_nightscout_json.cpp` and `test_panel_bitmap.cpp` sit beside it. `make -C firmware/xteink test` first checks that `lib/panel_bitmap` mentions no `float`, `double`, `new` or `malloc` and that the font header is current, then generates a header from `spec/display_vectors.json`, compiles the rules and tests with `-Wall -Wextra -Werror -Wconversion -Wshadow` plus AddressSanitizer and UBSan, and runs them on a PC. The current run reports 294 checks and 39 shared vectors with no failures, plus 2,970 checks for the Nightscout JSON parser (39 shared response cases and a fuzz pass of about 17,600 mutated bodies), plus 2,744 checks for the panel rasterizer. `make coverage` reports 100% of lines and 113 of 114 branches for the rules, and the test asserts the vectors' `spec_version`. `make format-check` confirms the code matches `.clang-format` (Google base, 100 columns). Both run in CI and in pre-commit.

The rules are proven identical to the Python and Swift versions by the shared vectors, which is the point of the design. See [[Testing and Quality]].

## What does not exist yet

A working device. Everything the hardware needs that a PC does not is still to be written: Wi-Fi, the HTTPS fetch with the readable token, the panel driver (Eric chooses between a home-grown SSD16xx driver and GxEPD2), deep sleep with real data, and the stamp with a trusted clock. Nothing is drawn on a panel yet. This is requirement FR-010, still Planned, and coverage gap GAP-005, rated High because host tests cannot cover it; the rasterizer and the skeleton closed part of it. The rest continues once the hardware is on the bench. The flashing procedure for the Xteink is also unwritten; it will follow CrossPoint's flashing and recovery guides, with the SD card backed up first and the image checked against the model.

## The bench board

Development happens on a Waveshare ESP32-S3-ePaper-1.54, not on the device the person with diabetes carries. It needs a 3.7 V LiPo with an MX1.25 connector and a USB-C data cable; hold BOOT while powering on to enter download mode. PlatformIO (the VS Code extension works on Windows) is the build tool: `cd firmware/xteink && pio run -e bench_s3 -e x4` builds both boards, `pio run -e bench_s3 -t upload` flashes the bench board, and `pio device monitor -e bench_s3` shows the dump, which repeats every minute. `platformio.ini` assumes 8 MB of flash for the bench board and 4 MB for the X4; both are board defaults still to be checked before the first upload. [[Hardware]] has the part names.

## WaveshareMon as prior art

The bench board is the exact board WaveshareMon uses, which makes that project the closest prior art and the first thing to study before writing device code. It demonstrates deep sleep, redrawing only on change, encrypted configuration, secrets never read back out of the device, and TLS on by default. [[Community Research]] compares it with the other open source displays, most of which are dormant, and suggests interoperating with its configuration schema rather than inventing another.

## Next steps, in order

1. Buy the bench board, battery, and cable, then the Xteink X4 Pro ([[Hardware]], Tier 1).
2. Flash the skeleton to the bench board after checking its flash size, and confirm the NO DATA dump (`crc32 3339447321`, ink 2,386) over USB serial.
3. Wi-Fi with exponential backoff and a visible "offline since" on the panel, so a connectivity failure never looks like a fresh reading. FR-015, still planned, covers that device-status line.
4. HTTPS GET to `/api/v1/entries/sgv.json` with the readable token, under the same rules as the Python client: HTTPS only, bounded count, timeout, no downgrade redirects. Never `setInsecure`; the token lives only in NVS and the `api-secret` header. See [[Security and Privacy]].
5. Feed the body to `lib/nightscout_json` (which runs `parse_entry` on each entry), then `classify` and `render`, then `render_panel` and the panel driver. Anything the device cannot verify (no Wi-Fi, bad clock, bad JSON) must end up as NO DATA or STALE on screen, never as a stale number that looks current. When `render_panel` refuses, blank the panel, because e-ink keeps its last image. Draw a stamp only with a trusted clock, and draw a "not updating" screen before sleep.
6. Deep sleep between updates, redraw on change plus a periodic age tick, and measured battery life published in the docs.
7. ADR-0006's promotion criteria: every vector state rendered correctly on the panel, a 24-hour soak without freezing, and one full sensor session beside the primary app with no mismatch, freeze, or missed STALE. Eric runs the validation; the person with diabetes decides whether to rely on the device.

## Rules for anyone touching this code

Same behavior as Python and Swift, always: change a rule in every implementation in the same commit and add or update a vector that pins it ([[Contributing]]). No dynamic allocation in `glucose_rules` or `panel_bitmap`, and no floating point in `panel_bitmap`. A panel layout change goes into `panel_layout.py` and `panel_bitmap.cpp` together, and `python tools/gen_panel_spec.py` re-pins the pixels. Any change to parsing, classification, or rendering is a hazard review trigger in `docs/SAFETY.md` ([[Safety]]).

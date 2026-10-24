# Firmware

The firmware is the pocket-display port of Lightkeeper: the same safety rules running on an Xteink X4 or X3 e-ink reader, built around an ESP32-C3 with Wi-Fi and Bluetooth. It reads Nightscout over Wi-Fi with the readable token and never talks to the sensor or the pump (ADR-0004). The source is `firmware/xteink/` in the repository, with its own README; the decision behind it is ADR-0006, summarized in [[Architecture Decisions]].

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Why an Xteink, and why C++

The goal is a small dedicated e-ink display that fits in a pocket. The Xteink X4 and X3 use an ESP32-C3, and an open source community firmware (CrossPoint) already exists for them, so custom firmware is realistic. A Raspberry Pi with an e-paper HAT runs the Python code unchanged but is not pocketable; it remains the plan for the bedside display. MicroPython was rejected as harder to verify than C++ with host tests. The device only works where it has Wi-Fi, which limits it to a convenience display, the role ADR-0004 allows.

## What exists today

`firmware/xteink/lib/glucose_rules/` holds `glucose_rules.h` and `glucose_rules.cpp`: the parse, classify, and render rules ported from `src/lightkeeper/domain/` to dependency-free C++17. No heap, no Arduino, fixed-size buffers (four lines of 32 characters including the terminator), and strings that are truncated rather than overflowed. The constants mirror the Python: sentinels at 39 and 401, a 2-minute future skew allowance, a 4-line limit, timestamps bounded to 2000 to 2100, and NaN rejected before any cast. Function names mirror the Python too (`parse_entry`, `classify`, `render`, `Level::Stale`; `newest_reading` is `parse_entries(...)[0]`), per ADR-0007, so the two can be reviewed side by side.

`firmware/xteink/test/host/test_glucose_rules.cpp` is the host test. `make -C firmware/xteink test` generates a header from `spec/display_vectors.json`, compiles the rules and tests with `-Wall -Wextra -Werror -Wconversion -Wshadow` plus AddressSanitizer and UBSan, and runs them on a PC. The current run reports 287 checks and 39 shared vectors with no failures, and the test asserts the vectors' `spec_version`. `make format-check` confirms the code matches `.clang-format` (Google base, 100 columns). Both run in CI and in pre-commit.

The rules are proven identical to the Python and Swift versions by the shared vectors, which is the point of the design. See [[Testing and Quality]].

## What does not exist yet

The device project. Everything the hardware needs that a PC does not is still to be written: Wi-Fi setup, an HTTPS fetch with the readable token, JSON field extraction, e-paper drawing, and deep sleep between updates. This is requirement FR-010 and coverage gap GAP-005, rated High because host tests cannot cover it. It starts once the hardware is on the bench. The flashing procedure for the Xteink is also unwritten; it will follow CrossPoint's flashing and recovery guides, with the SD card backed up first and the image checked against the model.

## The bench board

Development happens on a Waveshare ESP32-S3-ePaper-1.54, not on the device the person with diabetes carries. It needs a 3.7 V LiPo with an MX1.25 connector and a USB-C data cable; hold BOOT while powering on to enter download mode. PlatformIO (the VS Code extension works on Windows) is the build tool. [[Hardware]] has the part names.

## WaveshareMon as prior art

The bench board is the exact board WaveshareMon uses, which makes that project the closest prior art and the first thing to study before writing device code. It demonstrates deep sleep, redrawing only on change, encrypted configuration, secrets never read back out of the device, and TLS on by default. [[Community Research]] compares it with the other open source displays, most of which are dormant, and suggests interoperating with its configuration schema rather than inventing another.

## Next steps, in order

1. Buy the bench board, battery, and cable, then the Xteink X4 Pro ([[Hardware]], Tier 1).
2. Add a PlatformIO project for the ESP32-C3 beside `lib/glucose_rules`, leaving the rules library pure.
3. Wi-Fi with exponential backoff and a visible "offline since" on the panel, so a connectivity failure never looks like a fresh reading (FR-015 covers the device-status line).
4. HTTPS GET to `/api/v1/entries/sgv.json` with the readable token, under the same rules as the Python client: HTTPS only, bounded count, timeout, no downgrade redirects. See [[Security and Privacy]].
5. JSON field extraction into `newest_reading` (which runs `parse_entry` on each entry), then `classify` and `render`, then draw. Anything the device cannot verify (no Wi-Fi, bad clock, bad JSON) must end up as NO DATA or STALE on screen, never as a stale number that looks current.
6. Deep sleep between updates, redraw on change plus a periodic age tick, and measured battery life published in the docs.
7. ADR-0006's promotion criteria: every vector state rendered correctly on the panel, a 24-hour soak without freezing, and one full sensor session beside the primary app with no mismatch, freeze, or missed STALE. Eric runs the validation; the person with diabetes decides whether to rely on the device.

## Rules for anyone touching this code

Same behavior as Python and Swift, always: change a rule in every implementation in the same commit and add or update a vector that pins it ([[Contributing]]). No dynamic allocation in `glucose_rules`. Any change to parsing, classification, or rendering is a hazard review trigger in `docs/SAFETY.md` ([[Safety]]).

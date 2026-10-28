# Xteink e-ink firmware (groundwork)

Firmware for a pocket e-ink glucose display on the Xteink X4 or X3 (ESP32-C3, Wi-Fi and Bluetooth), reading Nightscout over Wi-Fi. It never talks to the sensor or the pump (ADR-0004).

**The device draws nothing on a panel yet.** The skeleton in `src/` builds for the bench board and the X4, renders the NO DATA screen, and prints it over USB serial. There is no e-paper driver, no Wi-Fi, no clock, and no Nightscout fetch. Do not carry it as a glucose display.

## Status

- [x] `lib/glucose_rules`: the safety rules (parse, classify, render) ported from `lightkeeper` to dependency-free C++17. No heap, no Arduino, fixed-size buffers.
- [x] Host tests run on a PC with AddressSanitizer and UBSan, including every shared vector in `spec/display_vectors.json` and every case in `spec/response_vectors.json`, so this code and the Python code reach identical conclusions and render identical screens.
- [x] `lib/nightscout_json`: a strict, streaming, heap-free parser for the raw Nightscout response. It finds the newest trustworthy reading with the same rules as Python's `json.loads` plus `parse_entries`, checked against the shared response corpus (`spec/response_vectors.json`) and fuzzed with thousands of mutated bodies under the sanitizers.
- [x] `lib/panel_bitmap`: the 1-bit panel rasterizer, a port of the Python reference (`panel_layout.py` and `epaper_bitmap.py`) with integers only, no heap, and no floating point. It draws every case in `spec/panel_vectors.json` (each display vector at each of the six panel profiles, plus the stamped cases) pixel for pixel: the host tests compare the CRC-32 and ink count of every image. The Keeper 5x8 font is compiled in from `spec/font5x8.json`.
- [x] Device skeleton (`src/`, PlatformIO, build only): the bench ESP32-S3 and the Xteink X4 link the three libraries above, not copies. With no network and no clock it can only show NO DATA, never a reading, and it prints that screen as `#`/`.` rows over USB serial, then deep sleeps for 60 seconds.
- [ ] Device step L-08: an e-paper driver (D11: a home-grown SSD16xx driver or GxEPD2 under GPL-3.0, with the X4's panel controller confirmed on the bench), Wi-Fi setup, HTTPS to Nightscout with the pinned CA and the readable token only in NVS and the `api-secret` header (ADR-0009, never `setInsecure()`), and the drawn-at stamp plus a "not updating" screen before sleeping, because e-ink keeps its last image. See `ADR-0006`.

## Layout

| Path | What it is |
| --- | --- |
| `lib/glucose_rules/` | The display rules, shared vectors with Python and Swift |
| `lib/nightscout_json/` | The Nightscout response parser |
| `lib/panel_bitmap/` | The panel rasterizer; `font5x8_data.h` is generated (see below) |
| `src/main.cpp` | The device skeleton: NO DATA, rasterize, serial dump, deep sleep |
| `src/serial_panel.*` | The lo-fi bench "driver": the screen as `#`/`.` rows over serial |
| `src/device_config.h` | Panel sizes and pin placeholders per board, every one marked VERIFY |
| `test/host/` | Host tests (`make test`) |
| `tools/` | Generators for the test includes and the font header |
| `platformio.ini` | The two device builds, `bench_s3` and `x4` |

## Run the tests

Needs `g++` (or `clang++`), `make`, and Python 3.11 or later. Linux, macOS, or WSL on Windows (MinGW toolchains (MSYS2, WinLibs, Git Bash) cannot link AddressSanitizer):

```bash
cd firmware/xteink
make test           # three suites under ASan and UBSan
make format-check   # clang-format, src/ included
make coverage       # gcov line and branch coverage of each library
```

`make test` also fails if `lib/panel_bitmap` mentions `float`, `double`, `new`, `delete`, `malloc` or `free` anywhere, comments included, or if the font header is out of date. On a mismatch the panel test writes the C++ image to `build/<vector>_<W>x<H>.pbm`, a 1-bit PBM any image viewer opens, to diff against the Python render (`render_bitmap(...).to_png()`).

## The font header

PlatformIO does not run make, so `lib/panel_bitmap/font5x8_data.h` is committed. When a glyph changes in `src/lightkeeper/infrastructure/font5x7.py`, regenerate the spec and then the header, and commit both:

```bash
python tools/gen_panel_spec.py                    # from the repository root
python firmware/xteink/tools/gen_font_header.py
```

Until then `tests/test_firmware_font.py` and `make test` fail.

## Build and flash the device skeleton

Needs [PlatformIO Core](https://platformio.org) 6.2.0 (`python -m pip install platformio==6.2.0`). The first build downloads the pinned platform (espressif32 7.1.3, which brings Arduino-ESP32 2.0.17 and GCC 8.4.0) into `~/.platformio`; after that it builds offline.

```bash
cd firmware/xteink
pio run                          # both boards: bench_s3 and x4
pio run -e bench_s3 -t upload    # flash the bench board over USB-C
pio device monitor -e bench_s3   # watch the dump; it repeats every minute
```

Flash the bench board, not the X4 the person with diabetes carries (docs/HARDWARE.md). Before flashing an X4, back up its SD card and follow the CrossPoint recovery notes, as docs/HARDWARE.md says. `.github/workflows/firmware-device.yml` builds both boards on every firmware change and fails on any compiler warning.

Every wake prints the board, the screen lines, the image's CRC-32 and ink count, and then one row of `#` (ink) and `.` (paper) per panel row. Compare the CRC-32 with the `no_data_unreachable` case at that profile in `spec/panel_vectors.json`:

| Board | Panel | CRC-32 | Ink pixels |
| --- | --- | --- | --- |
| `bench_s3` | `waveshare_1in54`, 200x200 | 3339447321 (0xc70bec19) | 2,386 |
| `x4` | `waveshare_7in5`, 800x480 | 4022210070 (0xefbe0e16) | 43,106 |

Serial is the board's native USB port (`ARDUINO_USB_CDC_ON_BOOT=1`, VERIFY on both boards); the port drops during each deep sleep and `pio device monitor` reconnects to it. The panel sizes and every pin in `src/device_config.h` are placeholders marked VERIFY: no pin is used yet, and the e-paper driver must not use one until it is checked on the bench.

## Memory

Measured with `pio run` on 2026-10-28 (PlatformIO 6.2.0, espressif32 7.1.3, Arduino-ESP32 2.0.17). RAM is static data and `.bss`, before the heap and the task stacks; the panel buffer is 60,000 bytes of it, sized for the largest pinned profile (the 600x800 Kindle) so any profile fits.

| Board | Chip | RAM used | Flash used (app partition) |
| --- | --- | --- | --- |
| `bench_s3` | ESP32-S3, 8 MB flash | 80,372 of 327,680 bytes (24.5%) | 290,637 of 3,342,336 bytes (8.7%) |
| `x4` | ESP32-C3, 4 MB flash (VERIFY) | 75,696 of 327,680 bytes (23.1%) | 273,896 of 1,310,720 bytes (20.9%) |

The builds use `-std=gnu++17 -Wall -Wextra` and print no warnings. The Arduino framework adds `-Wno-format`, `-Wno-sign-compare` and `-Wno-unused-parameter` after them; the host build (`-Werror -Wconversion -Wshadow`, ASan, UBSan) is the strict one for the libraries.

## Rules for this code

- Same behavior as Python, always. Change a rule in both places in the same commit, and add a vector to `spec/display_vectors.json` that pins it. The same holds for the panel: a layout change goes into `panel_layout.py` and `panel_bitmap.cpp` together, and `python tools/gen_panel_spec.py` re-pins the pixels.
- No dynamic allocation in `glucose_rules`, `nightscout_json` or `panel_bitmap`. `glucose_rules` puts every string into a fixed buffer and truncates it, never overflows it. `panel_bitmap` draws into a buffer the caller owns and checks every argument before the first byte is written; what it cannot draw exactly as Python would (a refused size, a bad stamp, a byte outside ASCII, a short buffer) it refuses, leaving the buffer untouched.
- `panel_bitmap` is integer arithmetic only: no floating point and no rounding, so it cannot drift a pixel from Python.
- Anything the device can't verify (no Wi-Fi, bad clock, bad JSON) must end up as NO DATA or STALE on screen, never as a stale number that looks current.
- No credentials in source. The Nightscout URL and token will live in NVS on the device, and the token travels only in the `api-secret` header (ADR-0009).

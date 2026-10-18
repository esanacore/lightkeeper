# Xteink e-ink firmware (groundwork)

Firmware for a pocket e-ink glucose display on the Xteink X4 or X3 (ESP32-C3, Wi-Fi and Bluetooth), reading Nightscout over Wi-Fi. It never talks to the sensor or the pump (ADR-0004).

## Status

- [x] `lib/glucose_rules`: the safety rules (parse, classify, render) ported from `glucose_watch` to dependency-free C++17. No heap, no Arduino, fixed-size buffers.
- [x] Host tests run on a PC with AddressSanitizer and UBSan, including every shared vector in `spec/display_vectors.json`, so this code and the Python code render identical screens.
- [ ] Device project (PlatformIO, ESP32-C3): Wi-Fi setup, HTTPS fetch with a readable token, JSON field extraction, e-paper drawing, deep sleep between updates. Starts once the hardware is on the bench; see `ADR-0006`.

## Run the tests

Needs `g++` (or `clang++`), `make`, and Python 3. Linux, macOS, WSL, or Git Bash on Windows:

```bash
cd firmware/xteink
make test
```

## Rules for this code

- Same behavior as Python, always. Change a rule in both places in the same commit, and add a vector to `spec/display_vectors.json` that pins it.
- No dynamic allocation in `glucose_rules`; every string goes into a fixed buffer and is truncated, never overflowed.
- Anything the device can't verify (no Wi-Fi, bad clock, bad JSON) must end up as NO DATA or STALE on screen, never as a stale number that looks current.

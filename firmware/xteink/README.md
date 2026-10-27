# Xteink e-ink firmware (groundwork)

Firmware for a pocket e-ink glucose display on the Xteink X4 or X3 (ESP32-C3, Wi-Fi and Bluetooth), reading Nightscout over Wi-Fi. It never talks to the sensor or the pump (ADR-0004).

## Status

- [x] `lib/glucose_rules`: the safety rules (parse, classify, render) ported from `lightkeeper` to dependency-free C++17. No heap, no Arduino, fixed-size buffers.
- [x] Host tests run on a PC with AddressSanitizer and UBSan, including every shared vector in `spec/display_vectors.json` and every case in `spec/response_vectors.json`, so this code and the Python code reach identical conclusions and render identical screens.
- [x] `lib/nightscout_json`: a strict, streaming, heap-free parser for the raw Nightscout response. It finds the newest trustworthy reading with the same rules as Python's `json.loads` plus `parse_entries`, checked against the shared response corpus (`spec/response_vectors.json`) and fuzzed with thousands of mutated bodies under the sanitizers.
- [ ] Device project (PlatformIO, ESP32-C3): Wi-Fi setup, HTTPS fetch with the readable token in the `api-secret` header (ADR-0009), e-paper drawing, deep sleep between updates. Starts once the hardware is on the bench; see `ADR-0006`.

## Run the tests

Needs `g++` (or `clang++`), `make`, and Python 3. Linux, macOS, or WSL on Windows (MinGW toolchains (MSYS2, WinLibs, Git Bash) cannot link AddressSanitizer):

```bash
cd firmware/xteink
make test
```

## Rules for this code

- Same behavior as Python, always. Change a rule in both places in the same commit, and add a vector to `spec/display_vectors.json` that pins it.
- No dynamic allocation in `glucose_rules`; every string goes into a fixed buffer and is truncated, never overflowed.
- Anything the device can't verify (no Wi-Fi, bad clock, bad JSON) must end up as NO DATA or STALE on screen, never as a stale number that looks current.

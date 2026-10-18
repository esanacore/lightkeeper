# TODO

The living roadmap. The phased rollout plan is in `docs/MVP_BACKLOG.md`; this file tracks concrete work items.

## Features

- [ ] Raspberry Pi e-paper display adapter for `glucose_watch` (FR-007).
- [ ] Home Assistant integration: publish level, value, and age as a sensor, alert on URGENT LOW and STALE (FR-008).
- [ ] Optional mmol/L display units.
- [ ] Show a short sparkline or delta from the previous reading.

## Technical Debt

- [ ] The Nightscout v1 API takes the token as a query parameter. Evaluate the v3 API with JWT bearer auth so the token never appears in URLs or proxy logs.

## Refactoring

- [ ] Split rendering profiles (terminal, e-ink 2.13", e-ink 4.2") once a second display exists.

## Testing

- [ ] GAP-001: hardware-in-the-loop check for the e-paper panel (FR-007).
- [ ] GAP-002: Home Assistant integration tests (FR-008).
- [ ] GAP-003: end-to-end tests against a disposable Nightscout instance with simulated uploads.
- [ ] GAP-004: multi-day `--watch` soak test for memory growth and clock drift.
- [ ] Add a Python setup step to `.github/workflows/constitution-tests.yml` and switch it to `--strict`.

## Documentation

- [ ] Fill in exact Nightscout deployment steps once the hosting choice is made (`docs/SETUP.md`).
- [ ] Record Trio build and settings notes from the first build.
- [ ] Kaitlin reviews `docs/SAFETY.md` and the default thresholds.

## Nice-to-Have

- [ ] ESP32 e-ink firmware port once the rules are proven in Python (ADR-0005). Candidate hardware: Xteink X4 or X3 pocket e-ink reader (ESP32-C3, Wi-Fi and BLE, open source CrossPoint firmware exists to build from). Port the domain rules and their tests first; it reads Nightscout over Wi-Fi only.
- [ ] Decide CGM: stay on Dexcom G7 or move to FreeStyle Libre 3 Plus, which Trio reads directly with no vendor app (see ADR-0002). Kaitlin's call with her endo and insurance.
- [ ] Contribute test logs and bug reports to the Trio Omnipod 5 beta.
- [ ] Revisit an Android collector with xDrip+ and AndroidAPS once AndroidAPS supports Omnipod 5.

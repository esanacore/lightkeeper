# TODO

The living roadmap. The phased rollout plan is in `docs/MVP_BACKLOG.md`; this file tracks concrete work items.

## Features

- [ ] Raspberry Pi e-paper display adapter for `lightkeeper` (FR-007).
- [ ] Home Assistant integration: publish level, value, and age as a sensor, alert on URGENT LOW and STALE (FR-008).
- [ ] Optional mmol/L display units.
- [ ] Show a short sparkline or delta from the previous reading.
- [ ] Draw `render_svg` output to a real e-paper bitmap for the Pi adapter (FR-007), reusing the gallery layout.

## Technical Debt

- [ ] The Nightscout v1 API takes the token as a query parameter. Evaluate the v3 API with JWT bearer auth so the token never appears in URLs or proxy logs.
- [ ] Upstream: the constitution's `constitution-env.yml` template calls `scripts/check_env_vars.sh` instead of `constitution/scripts/check_env_vars.sh`, so it silently skips in every adopter. Fixed locally; propose the fix in the engineering-constitution repo.
- [ ] Decide whether to keep the gstack section in `CLAUDE.md` (gstack is not installed in cloud sessions).

## Refactoring

- [ ] Split rendering profiles (terminal, e-ink 2.13", e-ink 4.2") once a second display exists.

## Testing

- [ ] GAP-001: hardware-in-the-loop check for the e-paper panel (FR-007).
- [ ] GAP-002: Home Assistant integration tests (FR-008).
- [ ] GAP-004: multi-day `--watch` soak test for memory growth and clock drift.
- [~] GAP-003: localhost fake Nightscout covers the HTTP layer; still need a real Nightscout instance.
- [ ] GAP-005: Xteink device build and on-hardware tests (FR-010).
- [ ] GAP-006: measure firmware coverage with gcov.

## Documentation

- [ ] Fill in exact Nightscout deployment steps once the hosting choice is made (`docs/SETUP.md`).
- [ ] Record Trio build and settings notes from the first build.
- [ ] Kaitlin reviews `docs/SAFETY.md` and the default thresholds.
- [ ] Publish `demo.html` on GitHub Pages and link it from the README's Demo section.
- [ ] Add a version line to the README (needs Eric's OK per the README house style in `docs/MEMORY.md`).

## Nice-to-Have

- [~] Xteink X4/X3 pocket display (ADR-0006): safety rules ported to C++ with host tests and shared vectors. Next: buy the device, add the PlatformIO ESP32-C3 project (Wi-Fi, HTTPS, JSON, e-paper, deep sleep).
- [ ] Decide CGM: stay on Dexcom G7 or move to FreeStyle Libre 3 Plus, which Trio reads directly with no vendor app (see ADR-0002). Kaitlin's call with her endo and insurance.
- [ ] Contribute test logs and bug reports upstream to Trio's Omnipod 5 driver (released in Trio v1.0.0).
- [ ] Revisit an Android collector with xDrip+ and AndroidAPS once AndroidAPS supports Omnipod 5.

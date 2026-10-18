# Product Requirements

This document translates product intent into concrete implementation requirements. Each requirement carries a stable ID and explicit acceptance criteria. The mapping from requirement to verifying test is tracked in `docs/REQUIREMENTS_TRACEABILITY.md`.

## Requirement Levels

- `MUST`: Required for the current release or MVP.
- `SHOULD`: Important, but can be deferred if needed.
- `COULD`: Useful future enhancement.
- `WON'T`: Explicitly out of scope for the current release or MVP.

## Requirement Identifiers

- Functional requirements use `FR-`, non-functional use `NFR-`.
- Acceptance criteria use sub-identifiers such as `FR-001-AC-1`.
- IDs are stable and never reused.

## Product Summary

An open source stack for managing Kaitlin's type 1 diabetes with community tools (Trio, Nightscout) instead of the stock Dexcom and Omnipod experience, plus our own read-only displays. Users: Kaitlin first, Eric as builder and secondary viewer, and later anyone in the community. Current release goal (0.1.0): a trustworthy, tested `lightkeeper` that can drive a text display from Nightscout, and the documentation to stand up Nightscout and Trio.

## Functional Requirements

### Reading Glucose Data

**FR-001** `MUST` Parse Nightscout sensor glucose entries and reject anything untrustworthy.

- Level: `MUST`
- Acceptance criteria:
  - `FR-001-AC-1`: Entries of type `sgv` with a whole-number value from 39 to 401 mg/dL and a positive millisecond timestamp parse into a reading with a UTC timestamp.
  - `FR-001-AC-2`: Entries with missing, non-numeric, fractional, or out-of-range values, a non-`sgv` type, or a bad timestamp are rejected, not repaired.
  - `FR-001-AC-3`: An unknown trend direction keeps the number and shows an unknown arrow.

### Classifying Status

**FR-002** `MUST` Classify a fresh reading as URGENT LOW, LOW, IN RANGE, HIGH, or URGENT HIGH using configurable thresholds (defaults 55 / 70 / 180 / 250 mg/dL).

- Level: `MUST`
- Acceptance criteria:
  - `FR-002-AC-1`: Boundary values classify as documented (55 urgent low, 70 in range, 180 in range, 181 high, 250 urgent high).

**FR-003** `MUST` Never present stale or future-dated data as current.

- Level: `MUST`
- Acceptance criteria:
  - `FR-003-AC-1`: A reading older than the stale limit (default 15 minutes) is STALE, regardless of its value.
  - `FR-003-AC-2`: A reading more than 2 minutes in the future is STALE.
  - `FR-003-AC-3`: No reading at all is NO DATA.

### Displaying

**FR-004** `MUST` Render a status as at most four short ASCII lines suitable for a small e-ink display.

- Level: `MUST`
- Acceptance criteria:
  - `FR-004-AC-1`: Fresh readings show level, value with trend arrow, and age.
  - `FR-004-AC-2`: STALE leads with "STALE - DO NOT TRUST" and the last value's age; STALE and NO DATA tell the user to confirm on the primary device.
  - `FR-004-AC-3`: Sensor sentinels render as "LOW (<40)" and "HIGH (>400)".

**FR-005** `MUST` Degrade safely when Nightscout is unreachable or returns bad data.

- Level: `MUST`
- Acceptance criteria:
  - `FR-005-AC-1`: Network errors, timeouts, and non-JSON or non-list responses never crash the program.
  - `FR-005-AC-2`: After a failure, the last good reading is re-classified against the current time, so it becomes STALE once old enough.

**FR-006** `MUST` Provide a command-line interface with an offline demo mode and meaningful exit codes.

- Level: `MUST`
- Acceptance criteria:
  - `FR-006-AC-1`: `--demo` runs with no network.
  - `FR-006-AC-2`: Exit code is 0 for fresh in-range, 1 for anything needing attention, 2 for configuration errors.
  - `FR-006-AC-3`: `--watch` refreshes no more often than every 15 seconds.

**FR-007** `SHOULD` Drive a physical e-ink display on a Raspberry Pi.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-007-AC-1`: The four rendered lines appear on the panel and refresh at least every 5 minutes.

**FR-008** `SHOULD` Publish status to Home Assistant for alerts and automations.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-008-AC-1`: Home Assistant shows a sensor with the level, value, and age, and can trigger an automation on URGENT LOW or STALE.

**FR-009** `MUST` Keep every display implementation in lockstep with the shared golden vectors.

- Level: `MUST`
- Acceptance criteria:
  - `FR-009-AC-1`: The Python suite and the firmware host tests both pass every case in `spec/display_vectors.json`, rendering identical level and lines.

**FR-010** `SHOULD` Run on an Xteink X4/X3 pocket e-ink reader over Wi-Fi.

- Level: `SHOULD`
- Acceptance criteria:
  - `FR-010-AC-1`: The device fetches from Nightscout, shows every vector state correctly, and updates at least every 5 minutes (ADR-0006).

## Non-Functional Requirements

### Security

**NFR-001** `MUST` Protect health data and Nightscout credentials.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-001-AC-1`: Only HTTPS URLs are accepted unless local testing is explicitly enabled in code.
  - `NFR-001-AC-2`: The token never appears in error messages or program output.

### Reliability

**NFR-002** `MUST` Reject invalid configuration at startup.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-002-AC-1`: Thresholds must satisfy 40 <= urgent low < low < high < urgent high <= 400 and a positive stale limit, or the program exits.

### Safety

**NFR-003** `MUST` Stay read-only.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-003-AC-1`: The client issues only GET requests to the `sgv` entries endpoint, with a bounded count.

### Testability

**NFR-004** `MUST` Keep the suite automated with at least 90% line and branch coverage, and 100% on the domain layer.

- Level: `MUST`
- Acceptance criteria:
  - `NFR-004-AC-1`: `python -m pytest --cov` passes and reports coverage at or above the floor.

## Explicit Non-Goals

- `WON'T` send any command to an insulin pump or calculate a dose (see `docs/SAFETY.md`).
- `WON'T` communicate with the Dexcom G7 sensor directly.
- `WON'T` write treatments or settings to Nightscout.
- `WON'T` replace the primary CGM app's alarms.

## Acceptance Criteria Summary

- [x] All `MUST` requirements for 0.1.0 (FR-001 to FR-006, FR-009, NFR-001 to NFR-004) have verifying tests and are `Verified` in `docs/REQUIREMENTS_TRACEABILITY.md`.
- [ ] Kaitlin has reviewed the default thresholds and stale limit.

## Traceability

Each requirement above is tracked to its verifying tests and status in `docs/REQUIREMENTS_TRACEABILITY.md`.

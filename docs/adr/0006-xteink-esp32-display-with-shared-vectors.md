# ADR-0006: Xteink ESP32-C3 Pocket Display, Kept in Lockstep with Python by Shared Vectors

Status: Proposed

Date: 2026-10-17

## Relationships

- Extends: ADR-0005
- Supersedes: none
- Related: ADR-0004, firmware/xteink/README.md, https://www.readme.club/firmware/crosspoint

## Promotion Criteria

- An Xteink X4 or X3 is on hand and confirmed flashable (community CrossPoint firmware shows the path).
- The device build fetches from the real Nightscout, renders every shared vector state correctly on the panel, and survives a 24-hour soak test without freezing.
- One full sensor session side by side with the primary app with no mismatch, freeze, or missed STALE.

- Gate: Eric runs the validation; Kaitlin decides whether she relies on the device.

## Context

Eric and Kaitlin want a small dedicated e-ink display. Xteink X4/X3 readers use an ESP32-C3 (Wi-Fi and Bluetooth) and have an open source community firmware, CrossPoint, so custom firmware is realistic. A second implementation of the display rules creates a new risk: the two implementations drifting apart, so the pocket display shows something the Python display wouldn't.

## Decision

- Target the Xteink X4/X3 for the first pocket display, reading Nightscout over Wi-Fi only.
- Port the domain rules to dependency-free C++17 (`firmware/xteink/lib/glucose_rules`) and test them on a PC with sanitizers.
- Keep one source of truth for behavior: `spec/display_vectors.json`. Both the Python suite and the C++ host tests must pass every vector. Any rule change adds or updates a vector in the same commit.

## Consequences

- Parity is enforced by tests, not by discipline. Writing the vectors already caught one real divergence: Python rendered five lines for STALE while Nightscout was unreachable, past the four-line limit; both now render four.
- The device only works where it has Wi-Fi (home, or a phone hotspot). That limits it to a convenience display, which is the role ADR-0004 allows.
- Device-only code (Wi-Fi, TLS, JSON, e-paper) still needs hardware testing; host tests can't cover it.

## Alternatives Considered

- **Generic mini e-readers with unknown chips:** no known way to load custom firmware.
- **Raspberry Pi Zero with an e-paper HAT:** runs the Python code unchanged, but bigger, hungrier, and not pocketable. Still the plan for the bedside display (FR-007).
- **MicroPython on the ESP32:** would share less code than it seems and has a heavier runtime; C++ with host tests is easier to verify.

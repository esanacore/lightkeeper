# MVP Backlog

The phased rollout of the whole stack. Phases gate on evidence, not dates. `TODO.md` holds individual work items.

## Phase 0: Foundation (this repository)

- [x] Bootstrap the repo with the engineering constitution.
- [x] Write the safety boundary, hazard log, and ADRs 0001 to 0005.
- [x] `lightkeeper` 0.1.0: parse, classify, render, degrade safely, with tests (FR-001 to FR-006).
- [ ] Kaitlin reviews `docs/SAFETY.md` and the default thresholds.

## Phase 1: Data Hub

- [ ] Choose hosting and deploy Nightscout over HTTPS, with authentication defaulted to deny (ADR-0003).
- [ ] Create a readable-role token for displays.
- [ ] Configure backups and test a restore.
- [ ] Run `lightkeeper` against it and close GAP-003.

## Phase 2: Trio in Open Loop

- [ ] Kaitlin talks with her endocrinologist about moving to Trio and reviews her current settings.
- [ ] Get an Apple Developer account and build Trio from source.
- [ ] Connect the Dexcom G7 app as the CGM source, turn off iOS automatic updates, and confirm Nightscout uploads.
- [ ] Pair Omnipod 5 pods with Trio (supported on main since Trio v1.0.0) in open loop, so Trio only suggests. Keep a backup DASH pod for the first switch, and don't fill the pod until Trio shows the pairing screen.
- [ ] Log every pod change, fault, and suggestion mismatch for at least two weeks.

## Phase 3: Closed Loop

- [ ] Settings validated with her care team; promotion criteria in ADR-0002 met.
- [ ] Enable closed loop conservatively, review data weekly at first.
- [ ] Keep the official Omnipod 5 app or Controller as a documented fallback.

## Phase 4: Our Hardware Layer

- [ ] Raspberry Pi e-paper bedside display (FR-007), side by side with the primary app for one full sensor session.
- [ ] Home Assistant sensor and alerts (FR-008).
- [x] ESP32 safety rules in C++ with shared-vector parity tests (ADR-0006).
- [ ] Xteink X4/X3 device build and side-by-side validation (FR-010).

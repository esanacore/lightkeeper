# ADR-0003: Self-Hosted Nightscout Is the Data Hub

Status: Proposed

Date: 2026-10-17

## Relationships

- Extends: ADR-0002
- Supersedes: none
- Related: ADR-0005, docs/OPERATIONS.md

## Promotion Criteria

- Nightscout is deployed with HTTPS, a strong API_SECRET, and authentication defaulted to deny.
- Trio is uploading and a readable-role token works with `lightkeeper`.
- Backups are configured and a restore has been tested once.

- Gate: Eric.

## Context

Every display, follower, and alert we build needs one source of glucose data that isn't the phone itself. Nightscout is the community standard, Trio uploads to it natively, and followers such as xDrip4iOS can read from it.

## Decision

Run our own Nightscout instance and treat it as the single data hub. All code in this repository reads from Nightscout with a token that has only the `readable` role.

## Consequences

- One integration point for every display and alert path.
- We own the uptime, security, and backups of health data. That is an operations responsibility, documented in `docs/OPERATIONS.md`.
- Displays depend on internet connectivity between the phone, Nightscout, and the display. That is why FR-003 and FR-005 exist.

## Alternatives Considered

- **Managed Nightscout hosting:** less operations work, but a third party holds the data. Acceptable fallback if self-hosting proves unreliable.
- **Dexcom Share follower APIs:** proprietary, the opposite of the project's goal.
- **Reading directly from the phone over the LAN:** no stable, documented interface, and it would not work away from home.

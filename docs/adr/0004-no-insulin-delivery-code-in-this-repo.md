# ADR-0004: No Insulin Delivery Code or Hardware in This Repository

Status: Accepted

Date: 2026-10-17

## Relationships

- Extends: none
- Supersedes: none
- Related: ADR-0002, docs/SAFETY.md

## Context

A fault in software or hardware that controls insulin delivery can kill someone. Community dosing apps have years of peer review, shared logs, and many users. A two-person repository does not, no matter how good the testing is.

## Decision

This repository will not contain code that commands a pump, calculates a dose, or changes therapy settings, and will not contain hardware designs for pumps, pump controllers, or pump radio bridges. It also will not talk to the CGM sensor directly. Contributions to dosing behavior go upstream to Trio (or AndroidAPS), through their review process.

## Consequences

- The blast radius of a bug in this repo is a wrong or missing number on a secondary display, which the hazard log mitigates.
- Some ideas are off the table here and must be pursued upstream instead.
- Changing this decision requires a new ADR, a hazard review in `docs/SAFETY.md`, and Kaitlin's explicit agreement.

## Alternatives Considered

- **Build our own dosing features here:** rejected for the reasons above.
- **Fork Trio into this repo:** rejected; contribute upstream instead so fixes reach everyone and get reviewed.

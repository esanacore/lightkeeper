# ADR-0005: Read-Only Display Layer in Python, Standard Library at Runtime

Status: Accepted

Date: 2026-10-17

## Relationships

- Extends: ADR-0003, ADR-0004
- Supersedes: none
- Related: docs/ARCHITECTURE.md

## Context

The first things we want to build are e-ink and bedside displays and Home Assistant alerts. Raspberry Pi e-paper HATs have mature Python drivers, Home Assistant is Python-based, and Python runs the same on Eric's Windows machine, a Mac, and a Pi.

## Decision

Build the display layer as a Python 3.11+ package (`lightkeeper`) with three layers: a pure domain layer with all safety rules, an application layer, and an infrastructure layer with a read-only HTTPS Nightscout client. Use only the standard library at runtime; test dependencies are pytest and pytest-cov.

## Consequences

- No third-party code in the data path, so the OTS inventory and supply-chain risk stay small.
- Safety rules are testable with plain data and a fixed clock, which is how we get 100% domain coverage.
- Display drivers (e-paper, Home Assistant) will be added as separate infrastructure adapters, each with its own OTS entry.

## Alternatives Considered

- **Node.js (same stack as Nightscout):** fine, but weaker e-paper driver support on the Pi.
- **Microcontroller firmware (ESP32):** lower power and cheaper, a good later target, but slower to iterate and harder to test. Revisit once the rules are proven in Python.

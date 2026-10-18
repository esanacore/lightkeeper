# ADR-0007: C++ Style, Google Base with Naming That Mirrors the Python

Status: Proposed

Date: 2026-10-18

## Relationships

- Extends: ADR-0006
- Supersedes: none
- Related: constitution/CODE_STYLE.md, firmware/xteink/.clang-format

## Promotion Criteria

- Eric approves the naming and column-limit deviations below. Gate: Eric.

## Context

`constitution/CODE_STYLE.md` points C++ at the Google C++ Style Guide. The firmware rules in `firmware/xteink/lib/glucose_rules` are a line-for-line port of the Python domain rules, and the shared vectors keep the two in lockstep. Reviewers compare them side by side, so matching names (`parse_entry`, `classify`, `render`, `Level::Stale`) make drift easier to spot than Google's `ParseEntry` and `kStale` would.

## Decision

- Format with clang-format, `BasedOnStyle: Google`, enforced by `make -C firmware/xteink format-check` and a pre-commit hook.
- Keep snake_case function names and CamelCase enum values that mirror the Python implementation.
- Use a 100-column limit (Google uses 80) to match the Python side's 99.
- Keep `#pragma once`, which every toolchain we target (GCC, Clang, the ESP32 toolchain) supports.

## Consequences

- One formatter, run automatically, settles layout questions.
- Code reads the same in both languages, which helps parity reviews.
- Anyone expecting strict Google naming will notice the difference; this ADR is where it's explained.

## Alternatives Considered

- **Strict Google style:** rename everything to PascalCase and `k`-prefixed enums. Rejected for now because it breaks the side-by-side reading with the Python code.
- **No formatter:** rejected; layout drift creates noisy diffs in safety-relevant code.

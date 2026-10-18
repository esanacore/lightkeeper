# Requirements Traceability Matrix

This matrix links each requirement to its acceptance criteria, the tests that verify it, and its current verification status. Update it in the same change that adds, modifies, or verifies a requirement.

Related documents:

- `docs/PRODUCT_REQUIREMENTS.md`: requirement definitions and IDs.
- `docs/TEST_PLAN.md`: coverage targets and the gap log.
- `docs/SAFETY.md`: hazards that each requirement mitigates.

## Conventions

- **Verifying tests** name the test file; individual tests are prefixed with the lowercase requirement ID (for example `test_fr003_...`), so `pytest -k fr003` runs everything for FR-003.
- **Status**: `Not Started`, `In Progress`, `Verified`, or `Deferred`.

## Functional Requirements

| Requirement ID | Level | Description | Acceptance Criteria | Verifying Tests | Status |
| --- | --- | --- | --- | --- | --- |
| FR-001 | MUST | Parse Nightscout entries, reject untrustworthy ones | FR-001-AC-1 to AC-3 | `tests/test_glucose.py` (`-k fr001`) | Verified |
| FR-002 | MUST | Classify fresh readings with configurable thresholds | FR-002-AC-1 | `tests/test_status.py` (`-k fr002`) | Verified |
| FR-003 | MUST | Never present stale or future data as current | FR-003-AC-1 to AC-3 | `tests/test_status.py`, `tests/test_monitor.py` (`-k fr003`) | Verified |
| FR-004 | MUST | Render short ASCII lines for e-ink | FR-004-AC-1 to AC-3 | `tests/test_monitor.py`, `tests/test_glucose.py` (`-k fr004`) | Verified |
| FR-005 | MUST | Degrade safely when Nightscout fails | FR-005-AC-1, AC-2 | `tests/test_monitor.py`, `tests/test_nightscout.py`, `tests/test_cli.py`, `tests/test_http_integration.py` (`-k fr005`) | Verified |
| FR-006 | MUST | CLI with demo mode and exit codes | FR-006-AC-1 to AC-3 | `tests/test_cli.py` (`-k fr006`) | Verified |
| FR-009 | MUST | Display implementations match shared vectors | FR-009-AC-1 | `tests/test_vectors.py`, `firmware/xteink/test/host/test_glucose_rules.cpp` (`make -C firmware/xteink test`) | Verified |
| FR-011 | SHOULD | SVG panel image, generated gallery and demo | FR-011-AC-1 to AC-3 | `tests/test_svg_display.py`, `tests/test_gallery.py` (`-k fr011`) | Verified |
| FR-012 | SHOULD | Read-only iOS companion app on the shared rules | FR-012-AC-1 to AC-3 | `apps/ios/LightkeeperCore/Tests/LightkeeperCoreTests/VectorTests.swift` (`.github/workflows/ios.yml`); AC-3 by code review of `apps/ios/` | Verified |

Planned requirements FR-007, FR-008, and FR-010 are reserved in `docs/PRODUCT_REQUIREMENTS.md` and get rows here when they are promoted (gaps GAP-001, GAP-002, GAP-005 in `docs/TEST_PLAN.md`).

## Non-Functional Requirements

| Requirement ID | Level | Description | Acceptance Criteria | Verifying Tests | Status |
| --- | --- | --- | --- | --- | --- |
| NFR-001 | MUST | HTTPS only, token never exposed | NFR-001-AC-1, AC-2 | `tests/test_nightscout.py`, `tests/test_cli.py` (`-k nfr001`) | Verified |
| NFR-002 | MUST | Reject invalid configuration | NFR-002-AC-1 | `tests/test_status.py`, `tests/test_cli.py` (`-k nfr002`) | Verified |
| NFR-003 | MUST | Read-only client, bounded requests | NFR-003-AC-1 | `tests/test_nightscout.py` (`-k nfr003`) | Verified |
| NFR-004 | MUST | Automated suite, 90% floor | NFR-004-AC-1 | `pytest --cov` with `fail_under = 90` in `pyproject.toml` | Verified |

## Coverage Summary

| Metric | Count |
| --- | --- |
| Total requirements | 13 (plus 3 planned) |
| Verified | 13 |
| In progress | 0 |
| Not started | 0 |
| Requirements without a verifying test (gaps) | 0 |

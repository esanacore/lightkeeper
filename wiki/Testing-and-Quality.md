# Testing and Quality

How the repository is tested, what it promises about coverage, and how a reader can check those promises. The source documents are `docs/TEST_PLAN.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, and `docs/PRODUCT_REQUIREMENTS.md` in the repository. Numbers are from the current 0.1.0 tree: 313 Python tests, 100% line and branch coverage, 39 shared vectors, 294 firmware checks.

## The pyramid

| Layer | What it covers | Where |
| --- | --- | --- |
| Unit | Domain rules with a fixed clock and plain data | `tests/test_glucose.py`, `tests/test_status.py` |
| Integration | Nightscout client against an injected fetcher, application layer against fakes, CLI end to end in demo mode | `tests/test_nightscout.py`, `tests/test_monitor.py`, `tests/test_cli.py` |
| HTTP integration | A fake Nightscout on localhost exercises the real urllib fetcher: status codes, timeouts, oversized bodies, HTML pages, redirects | `tests/test_http_integration.py` |
| Shared vectors | Every case in `spec/display_vectors.json`, run by Python, C++, and Swift | `tests/test_vectors.py`, `firmware/xteink/test/host/`, `apps/ios/LightkeeperCore/Tests/` |
| Firmware host tests | C++17 rules under AddressSanitizer and UBSan on a PC | `make -C firmware/xteink test` |
| iOS core tests | XCTest on GitHub's macOS runners | `.github/workflows/ios.yml` |
| Gallery and demo | Committed `docs/DISPLAY_STATES.md`, SVGs, and demo table match the generator | `tests/test_gallery.py` |
| Static analysis | ruff (pycodestyle, pyflakes, import order, PEP 257, bugbear, pyupgrade, bandit), ruff format, strict mypy on `src/`, clang-format | pre-commit and CI |
| End to end | A real self-hosted Nightscout with simulated uploads | planned, GAP-003 |
| Manual validation | A display beside the primary app for one full sensor session, logging any mismatch, freeze, or missed STALE | before anyone relies on a display |

Test names carry the requirement or hazard ID they verify, for example `test_fr003_staleness_beats_urgent_low` or `test_haz011_one_poisoned_entry_never_hides_the_good_ones`, so `pytest -k fr003` runs everything for FR-003. That naming is the mechanism behind traceability.

## Shared vectors and three-way parity

`spec/display_vectors.json` holds 39 cases. Each is either one raw Nightscout entry (or none) with its age in `minutes_ago` or `seconds_ago`, or an `entries` list in which every entry has its own age, so the same file covers the 15-minutes-plus-one-second boundary, same-timestamp ties, poisoned entries next to good ones, and newest-wins selection. A case can also carry custom `thresholds`. Each gives an optional fetch error and the exact expected level and lines. The file carries a `spec_version` (currently 1) that increments whenever an existing case changes; adding a case or an optional field does not bump it.

Three suites run every case, must produce identical output, and assert the spec version: `tests/test_vectors.py` (Python), the firmware host tests (C++, with the vectors compiled into a header by the Makefile), and `VectorTests.swift`. This is FR-009 for Python and C++ and FR-012 for Swift. Parity is enforced by tests rather than by discipline, and the vectors have caught real divergences: Python once rendered five lines for STALE while Nightscout was unreachable (`stale_while_unreachable_stays_four_lines`), and the firmware once passed a NaN through a cast by luck (`huge_value_rejected`, HAZ-011). Pictures are in [[Display States]].

## Coverage floors

| Scope | Metric | Floor | Current |
| --- | --- | --- | --- |
| Repository default | Line and branch | 90% (`fail_under` in `pyproject.toml`) | 100% |
| Domain layer (the safety rules) | Line and branch | 100% | 100% |
| Nightscout client | Line and branch | 95% | 100% |
| Firmware `glucose_rules` | Every shared vector plus edge cases | 100% of vectors | 294 checks pass; 100% of lines and 113 of 114 branches (gcov) |

Firmware coverage is measured with gcov: `make -C firmware/xteink coverage` reports 100% of lines and 113 of 114 branches in `glucose_rules.cpp`; the one branch left is a defensive guard that the public API cannot reach. The coverage history is a dated table in `docs/TEST_PLAN.md`.

## Requirements traceability

`docs/PRODUCT_REQUIREMENTS.md` defines each requirement with a stable ID, a MUST/SHOULD/COULD/WON'T level, and numbered acceptance criteria such as `FR-003-AC-2`. `docs/REQUIREMENTS_TRACEABILITY.md` maps each to its verifying tests and a status. For 0.1.0, FR-001 through FR-006, FR-009, FR-011, FR-012, and NFR-001 through NFR-004 are Verified, 13 in all. FR-007, FR-008, FR-010, FR-013, FR-014, and FR-015 are reserved in a Planned section and get rows when their first test lands. A constitution check fails the build if a declared requirement has no verifying test, which is why unstarted work is kept out of the declared list.

The gap log names what is not yet tested: GAP-001 physical e-paper output, GAP-002 a real Home Assistant check (fake-broker tests already run), GAP-003 a real Nightscout instance, GAP-004 a real-time multi-day `--watch` run on the Pi (an accelerated three-day soak already runs in the suite), GAP-005 the Xteink device build (High). GAP-006, firmware coverage measurement, was closed on 2026-10-25.

## The constitution CI checks

The repository adopts Eric's Engineering Constitution as a submodule, and its workflows run on every push and pull request: `constitution-tests.yml` runs the declared suite; `constitution-architecture.yml` verifies that layer dependencies point inward; `constitution-compliance.yml` checks governance files, a self-contained `demo.html`, the README's structure, and requirements traceability; `constitution-env.yml` checks `.env.example` and `docs/ENV_VARS.md` against the code; `constitution-secrets.yml` sweeps for secrets; `constitution-ots.yml` checks the OTS inventory; `constitution-doc-freshness.yml` flags source changes without documentation changes; `constitution-version.yml` checks the submodule is current; `constitution-wiki.yml` checks this wiki for dangling links and orphans and publishes it on merge. `ios.yml` builds and tests the Swift package on macOS runners. Actions are pinned by commit SHA.

## How to run everything

```bash
python tools/doctor.py
python -m ruff check . && python -m ruff format --check . && python -m mypy
python -m pytest --cov --cov-report=term-missing
make -C firmware/xteink format-check test
bash constitution/scripts/run_declared_tests.sh .
bash constitution/scripts/check_compliance.sh --product .
bash constitution/scripts/check_wiki_links.sh --strict .
```

## The mutation check

Coverage says a line ran, not that a test would notice if it were wrong. For the firmware rules a mutation check was done by hand and recorded in `docs/OTS_SOFTWARE.md` (OTS-106): a staleness comparison was deliberately broken and the host tests failed. There is no automated mutation tool. To repeat it on any implementation, flip one comparison in `classify` (`>=` for `>` on the stale check, or drop the future-skew branch), confirm the boundary vectors (`fresh_at_15_minutes`, `stale_at_16_minutes`, `small_clock_skew_ok`, `future_dated`) fail, then revert. A rule that does not fail at least one vector when mutated needs a new vector.

See [[Contributing]] for what a change must bring with it, and [[Safety]] for the hazards each test defends.

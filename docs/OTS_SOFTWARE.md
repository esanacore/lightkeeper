# OTS Software Inventory

This inventory tracks every off-the-shelf (OTS) software component this project depends on, following the intent of the FDA's OTS guidance and IEC 62304 SOUP requirements. It is a living document: update it in the same change that adds, removes, or upgrades a dependency.

Related documents: `constitution/SECURITY.md`, `docs/TEST_PLAN.md`, `docs/SAFETY.md`.

## Conventions

- **Component ID**: `OTS-001`, ... never reused. Removed components keep their row with Status `Removed`.
- **Name**: exactly as declared in the manifest (`pyproject.toml`).
- **Risk**: `Low`, `Medium`, or `High`. Anything in the therapy path is `High`.
- **Status**: `Active`, `Evaluating`, or `Removed`.

## Managed Dependencies

`lightkeeper` has no runtime dependencies. These are development and test tools only, declared under `[project.optional-dependencies] dev` in `pyproject.toml`.

| Component ID | Name | Version | Supplier / Maintainer | Purpose | License | Risk | Verification | Anomaly Review | Update Policy | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OTS-001 | pytest | >=8 | pytest-dev | Test runner | MIT | Low | Mature upstream suite; runs our 87 tests in CI | github.com/pytest-dev/pytest/issues, last reviewed 2026-10-17 | Range, Dependabot-managed | Active |
| OTS-002 | pytest-cov | >=5 | pytest-dev | Coverage measurement and floor | MIT | Low | Mature upstream suite; floor enforced via `fail_under` | github.com/pytest-dev/pytest-cov/issues, last reviewed 2026-10-17 | Range, Dependabot-managed | Active |

## System-Level OTS

Software the stack depends on that is not in a manifest. The therapy-path rows are not shipped by this repo, but they are tracked here because the whole system's safety depends on them.

| Component ID | Name | Version | Supplier / Maintainer | Purpose | License | Risk | Verification | Anomaly Review | Update Policy | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OTS-101 | Python | 3.11+ | Python Software Foundation | Runtime for lightkeeper | PSF-2.0 | Low | Test suite runs on it in CI | python.org security advisories, last reviewed 2026-10-17 | Track supported minor versions | Active |
| OTS-106 | GCC / Clang C++17 toolchain with ASan and UBSan | Distribution default | GNU / LLVM | Builds and runs firmware host tests | GPL-3.0-with-GCC-exception / Apache-2.0-with-LLVM-exception | Low | Sanitizers plus shared vectors; a mutation check confirmed the tests catch a staleness bug | Distribution advisories, last reviewed 2026-10-17 | CI runner default | Active |
| OTS-102 | Nightscout (cgm-remote-monitor) | Pin at deploy time | Nightscout Foundation | Data hub, source of all readings | AGPL-3.0 | Medium | E2E tests planned (GAP-003); read-only token scope | github.com/nightscout/cgm-remote-monitor/issues, last reviewed 2026-10-17 | Manual upgrades after release notes review | Evaluating |
| OTS-103 | Trio | Pin at build time | Trio community / Nightscout Foundation | Dosing controller on iPhone (ADR-0002) | AGPL-3.0 | High | Upstream review and testing; our open-loop validation phase | github.com/nightscout/Trio/issues and Trio Discord, last reviewed 2026-10-17 | Rebuild on release, after reading notes; never auto-update | Evaluating |
| OTS-104 | Dexcom G7 app | Current App Store release | Dexcom | Sensor radio on iPhone, read by Trio | Proprietary | High | Commercial, regulated device software | Dexcom notices; Trio community reports, last reviewed 2026-10-17 | Turn off iOS automatic updates; update only after the community confirms Trio compatibility | Active |
| OTS-105 | Omnipod 5 pods and Trio OmnipodKit driver | Open beta | Insulet (pods); open source developers (driver) | Insulin delivery | Proprietary (pods) / see upstream (driver) | High | Upstream beta testing; our pod-change log during rollout | nightscout.github.io/omnipod-five, last reviewed 2026-10-17 | Follow Trio releases | Evaluating |

## Review Cadence

- Review this inventory in the same change that adds, removes, or upgrades a dependency.
- Before every release, and before every Trio rebuild, re-check the High rows' trackers for new issues and refresh the dates.

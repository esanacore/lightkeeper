# OTS Software Inventory

This inventory tracks every off-the-shelf (OTS) software component this project depends on, following the intent of the FDA's OTS guidance and IEC 62304 SOUP requirements. It is a living document: update it in the same change that adds, removes, or upgrades a dependency.

Related documents: `constitution/SECURITY.md`, `docs/TEST_PLAN.md`, `docs/SAFETY.md`.

## Conventions

- **Component ID**: `OTS-001`, ... never reused. Removed components keep their row with Status `Removed`.
- **Name**: exactly as declared in the manifest (`pyproject.toml`).
- **Risk**: `Low`, `Medium`, or `High`. Anything in the therapy path is `High`.
- **Status**: `Active`, `Evaluating`, or `Removed`.

## Managed Dependencies

`lightkeeper` has no runtime dependencies. These are development, test, and static-analysis tools only, declared under `[project.optional-dependencies] dev` in `pyproject.toml` and updated by Dependabot's pip entry.

| Component ID | Name | Version | Supplier / Maintainer | Purpose | License | Risk | Verification | Anomaly Review | Update Policy | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OTS-001 | pytest | >=8 | pytest-dev | Test runner | MIT | Low | Mature upstream suite; runs our Python suite in CI | github.com/pytest-dev/pytest/issues, last reviewed 2026-10-17 | Range, Dependabot-managed | Active |
| OTS-002 | pytest-cov | >=5 | pytest-dev | Coverage measurement and floor | MIT | Low | Mature upstream suite; floor enforced via `fail_under` | github.com/pytest-dev/pytest-cov/issues, last reviewed 2026-10-17 | Range, Dependabot-managed | Active |
| OTS-003 | ruff | >=0.6 | Astral | Lint (incl. bandit security rules) and format | MIT | Low | Runs on every commit and in CI; findings reviewed by hand when first enabled | github.com/astral-sh/ruff/issues, last reviewed 2026-10-18 | Range, Dependabot-managed; pre-commit pin v0.16.8 | Active |
| OTS-004 | mypy | >=1.11 | Python typing community | Strict static type checking of `src/` | MIT | Low | Runs in the declared suite and pre-commit | github.com/python/mypy/issues, last reviewed 2026-10-18 | Range, Dependabot-managed | Active |
| OTS-005 | setuptools | >=69 | Python Packaging Authority | Build backend (already in `[build-system]`); also a dev extra so `tests/test_packaging.py` can build the wheel offline | MIT | Low | The same backend that builds every release; the packaging test checks its output | github.com/pypa/setuptools/issues, last reviewed 2026-10-27 | Range, Dependabot-managed | Active |

## System-Level OTS

Software the stack depends on that is not in a manifest. The therapy-path rows are not shipped by this repo, but they are tracked here because the whole system's safety depends on them.

| Component ID | Name | Version | Supplier / Maintainer | Purpose | License | Risk | Verification | Anomaly Review | Update Policy | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OTS-101 | Python | 3.11+ | Python Software Foundation | Runtime for lightkeeper | PSF-2.0 | Low | Test suite runs on it in CI | python.org security advisories, last reviewed 2026-10-17 | Track supported minor versions | Active |
| OTS-106 | GCC / Clang C++17 toolchain with ASan and UBSan | Distribution default | GNU / LLVM | Builds and runs firmware host tests | GPL-3.0-with-GCC-exception / Apache-2.0-with-LLVM-exception | Low | Sanitizers plus shared vectors; a mutation check confirmed the tests catch a staleness bug | Distribution advisories, last reviewed 2026-10-17 | CI runner default | Active |
| OTS-107 | clang-format | 18 (pre-commit pin v18.1.8) | LLVM | C++ formatting for the firmware | Apache-2.0 WITH LLVM-exception | Low | `make format-check` in the declared suite | github.com/llvm/llvm-project/issues, last reviewed 2026-10-18 | Pre-commit pin, manual bumps | Active |
| OTS-108 | actions/checkout | v7.0.1 (SHA-pinned) | GitHub | CI checkout with submodules | MIT | Medium | Pinned by full commit SHA; runs with read-only token except the wiki publish job | github.com/actions/checkout/issues, last reviewed 2026-10-18 | SHA pin, Dependabot github-actions | Active |
| OTS-109 | actions/setup-python | v7.1.0 (SHA-pinned) | GitHub | Python in the test workflow | MIT | Medium | Pinned by full commit SHA; read-only token | github.com/actions/setup-python/issues, last reviewed 2026-10-27 (v7.1.0 SHA verified against the tag) | SHA pin, Dependabot github-actions | Active |
| OTS-110 | pre-commit hooks (pre-commit-hooks, ruff-pre-commit, mirrors-clang-format) | v4.6.0, v0.16.8, v18.1.8 | pre-commit, Astral, LLVM mirrors | Local commit and push checks | MIT / Apache-2.0 | Low | Local only, never in the shipped package | Upstream trackers, last reviewed 2026-10-18 | Pinned revs, `pre-commit autoupdate` | Active |
| OTS-111 | XcodeGen | brew latest at CI time | yonaskolb | Generates the Xcode project from `project.yml` in CI | MIT | Low | Build succeeds in `ios.yml` | github.com/yonaskolb/XcodeGen/issues, last reviewed 2026-10-18 | Homebrew in CI; pin if a break appears | Active |
| OTS-112 | Xcode and Swift toolchain | Xcode 16.x on macos-15 runners | Apple | Builds and tests the iOS app and core package | Proprietary (Apple) | Low | CI | Apple release notes, last reviewed 2026-10-18 | Runner image default | Active |
| OTS-113 | Swift open-source toolchain (`swift` Docker image) | `swift:6.1-noble` tag | Swift project (swift.org) | Runs the LightkeeperCore tests on Linux in `ios.yml` to keep the rules portable | Apache-2.0 | Low | The same package tests that run on macOS; also verified locally with Swift 6.4 on Windows | swift.org security and release notes, last reviewed 2026-10-23 | Image tag in the workflow; bump deliberately | Active |
| OTS-114 | actions/upload-pages-artifact | v5.0.0 (SHA-pinned) | GitHub | Packages the demo site in `pages.yml` | MIT | Low | Pinned by full commit SHA; uploads one static file | github.com/actions/upload-pages-artifact/issues, last reviewed 2026-10-24 | SHA pin, Dependabot github-actions | Active |
| OTS-115 | actions/deploy-pages | v5.0.1 (SHA-pinned) | GitHub | Publishes the demo to GitHub Pages in `pages.yml` | MIT | Medium | Pinned by full commit SHA; the only job with `pages: write` and `id-token: write` | github.com/actions/deploy-pages/issues, last reviewed 2026-10-24 | SHA pin, Dependabot github-actions | Active |
| OTS-116 | OpenSCAD | 2021.01 (winget, installer hash verified) | OpenSCAD project | Renders the enclosure documentation images and exports its STLs (`tools/render_enclosure.py`); developer machine only, not shipped | GPL-2.0 | Low | Watertight STLs checked with trimesh; renders reviewed by eye | github.com/openscad/openscad/issues, last reviewed 2026-10-27 | Manual; re-render after an upgrade | Active |
| OTS-117 | @mermaid-js/mermaid-cli | 11.4.2 (npm, local, not committed) | Mermaid project | Renders `assets/diagrams/*.mmd` to SVG (`tools/render_diagrams.py`); developer machine only | MIT | Low | Deterministic: an unchanged source re-renders byte for byte | github.com/mermaid-js/mermaid-cli/issues, last reviewed 2026-10-27 | Pinned version on install | Active |
| OTS-118 | Pillow | 12.x (developer machine) | Python Pillow | Downsamples enclosure renders for anti-aliasing (`tools/render_enclosure.py`); not a runtime dependency | MIT-CMU | Low | Output reviewed by eye | github.com/python-pillow/Pillow/issues, last reviewed 2026-10-27 | Manual | Active |
| OTS-119 | Node.js | 20 or later (CI: 24 via actions/setup-node; Node 24 on the developer machine) | OpenJS Foundation | Runs `web/panel/panel.test.mjs` (`node --test`, no packages) through `tests/test_demo_panel.py`; test-time only, never shipped | MIT | Low | The CRC-32 check value and all 237 pixel vectors; a missing node fails CI | github.com/nodejs/node/issues, last reviewed 2026-10-28 | Major version pinned in `constitution-tests.yml` | Active |
| OTS-120 | actions/setup-node | v7.1.0 (SHA-pinned, 949feb2413d6458794dcd2491c4babbbce0c15c1) | GitHub | Node in the Constitution Test Runner | MIT | Medium | Pinned by full commit SHA, verified against the tag 2026-10-28; read-only token | github.com/actions/setup-node/issues, last reviewed 2026-10-28 | SHA pin, Dependabot github-actions | Active |
| OTS-121 | actions/cache | v6.1.0 (SHA-pinned, 55cc8345863c7cc4c66a329aec7e433d2d1c52a9) | GitHub | Caches `~/.platformio` in `firmware-device.yml` | MIT | Low | Pinned by full commit SHA (tag verified with gh api) | github.com/actions/cache/issues, last reviewed 2026-10-28 | SHA pin, Dependabot github-actions | Active |
| OTS-122 | PlatformIO Core | 6.2.0 (pip in CI; developer machine), with its SCons build engine (tool-scons 4.41101.0, MIT) | PlatformIO Labs | Builds the ESP32 device skeleton | Apache-2.0 | Low | `pio run -e bench_s3 -e x4` with zero warnings | github.com/platformio/platformio-core/issues, last reviewed 2026-10-28 | Pinned version in `firmware-device.yml` | Active |
| OTS-123 | platform-espressif32 | 7.1.3 | PlatformIO | Board definitions and build scripts | Apache-2.0 | Low | Same build | github.com/platformio/platform-espressif32/issues, last reviewed 2026-10-28 | Pinned in `platformio.ini` | Active |
| OTS-124 | Arduino-ESP32 (framework-arduinoespressif32) | 2.0.17 (package 4.20017.260907) | Espressif | The core linked into the firmware (Serial, deep sleep), including the precompiled ESP-IDF 4.4 libraries | LGPL-2.1-or-later (ESP-IDF Apache-2.0) | Medium (ships in the device image; LGPL relinking obligations apply if binaries are ever distributed) | Build with zero warnings under the framework's own suppressions | github.com/espressif/arduino-esp32/issues, last reviewed 2026-10-28 | Pinned through the platform | Active |
| OTS-125 | Espressif GCC toolchains (xtensa-esp32s3, riscv32-esp) | 8.4.0+2021r2-patch5 | Espressif | Cross-compilers for both boards | GPL-3.0-or-later with the GCC Runtime Library Exception (PlatformIO's package metadata lists GPL-2.0-or-later) | Low | Build only | github.com/espressif/crosstool-NG/issues, last reviewed 2026-10-28 | Pinned through the platform | Active |
| OTS-126 | esptool.py | 4.11.0 (package tool-esptoolpy 2.41100.260830) | Espressif | Flashing tool only | GPL-2.0-or-later | Low | Not yet used on hardware | github.com/espressif/esptool/issues, last reviewed 2026-10-28 | Pinned through the platform | Active |
| OTS-102 | Nightscout (cgm-remote-monitor) | Pin at deploy time | Nightscout Foundation | Data hub, source of all readings | AGPL-3.0 | Medium | E2E tests planned (GAP-003); read-only token scope | github.com/nightscout/cgm-remote-monitor/issues, last reviewed 2026-10-17 | Manual upgrades after release notes review | Evaluating |
| OTS-103 | Trio | Pin at build time | Trio community / Nightscout Foundation | Dosing controller on iPhone (ADR-0002) | AGPL-3.0 | High | Upstream review and testing; our open-loop validation phase | github.com/nightscout/Trio/issues and Trio Discord, last reviewed 2026-10-17 | Rebuild on release, after reading notes; never auto-update | Evaluating |
| OTS-104 | Dexcom G7 app | Current App Store release | Dexcom | Sensor radio on iPhone, read by Trio | Proprietary | High | Commercial, regulated device software | Dexcom notices; Trio community reports, last reviewed 2026-10-17 | Turn off iOS automatic updates; update only after the community confirms Trio compatibility | Active |
| OTS-105 | Omnipod 5 pods and Trio OmnipodKit driver | Trio v1.0.0+ (released 2026-09-15) | Insulet (pods); open source developers (driver) | Insulin delivery | Proprietary (pods) / see upstream (driver) | High | Upstream beta program completed before release; our pod-change log during rollout | nightscout.github.io/omnipod-five and its compatibility page, last reviewed 2026-10-18 | Follow Trio releases | Evaluating |

## Review Cadence

- Review this inventory in the same change that adds, removes, or upgrades a dependency.
- Before every release, and before every Trio rebuild, re-check the High rows' trackers for new issues and refresh the dates.

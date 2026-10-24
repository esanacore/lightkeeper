# Contributing

Lightkeeper follows Eric's Engineering Constitution, included as the `constitution/` git submodule, and the repository's own `.github/CONTRIBUTING.md`. This page is the practical version for someone opening a pull request. Because the code decides what a person with diabetes sees on a screen, the bar for a change is higher than its line count suggests.

## Before you start

Clone with `--recurse-submodules`, install with `pip install -e ".[dev]" pre-commit`, run `python tools/doctor.py`, then install the hooks:

```bash
pre-commit install && pre-commit install --hook-type pre-push
```

The commit hooks run ruff, ruff format, strict mypy, clang-format, syntax checks, and large-file and private-key detection; the push hook adds the constitution's secrets sweep. CI runs the same checks. [[Getting Started]] has the per-platform install steps.

If your change touches parsing, classification, rendering, the Nightscout client, or the firmware or Swift rules, read `docs/SAFETY.md` first. Those changes need a hazard review, described below.

## Commit messages

Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`, with `!` or a `BREAKING CHANGE` footer for incompatible changes. Release tooling reads the history to suggest version bumps; `CHANGELOG.md` remains the human-facing record and is updated by hand for every user-facing change. Keep the subject short and specific: `fix: STALE while unreachable renders four lines, not five`.

## The rule-change-in-one-commit requirement

Display behavior is implemented in four places that must agree, and the vectors are the source of truth. A change to any rule (a threshold boundary, the stale limit, the future-skew allowance, a line of rendered text, a parsing rejection) is one commit that touches all of them:

1. `src/lightkeeper/domain/` (Python).
2. `firmware/xteink/lib/glucose_rules/` (C++).
3. `apps/ios/LightkeeperCore/Sources/` (Swift).
4. `spec/display_vectors.json`: add a case that pins the new behavior, or update an existing one and bump `spec_version`, then update the version assertion in all three suites.
5. Run `python tools/gen_display_gallery.py` to regenerate `docs/DISPLAY_STATES.md`, the SVGs under `docs/img/display-states/`, and the state table in `demo.html`, and commit the result.

The suites enforce this: the three vector tests fail if an implementation disagrees, and `tests/test_gallery.py` fails if the gallery or demo drifts. If you cannot build one of the three locally (no Swift toolchain, say), say so in the pull request; CI runs the Swift tests on macOS and Linux, but the code still has to change. The Swift package also builds with the Windows Swift toolchain. [[How It Works]] explains why there are four places; [[Testing and Quality]] describes the parity tests.

## Hazard review

Any change that could affect what number or status a person sees gets a hazard review in the pull request:

- Identify which HAZ rows in `docs/SAFETY.md` the change touches, or add a new row with ID, hazard, cause, severity, likelihood, mitigation, and the verifying test.
- Name the requirement (`FR-` or `NFR-`) and acceptance criterion the change serves. New behavior gets a new requirement in `docs/PRODUCT_REQUIREMENTS.md` and a row in `docs/REQUIREMENTS_TRACEABILITY.md`, in the same change as its first test.
- Name the test with the requirement or hazard ID prefix, for example `test_fr003_...` or `test_haz011_...`, so `pytest -k` finds it.
- If the change would cross the safety boundary (talk to a pump or sensor, calculate a dose, write to Nightscout), stop. That needs a new ADR, a hazard review, and the agreement of the person whose data it shows. The default answer is no. See [[Safety]] and [[Architecture Decisions]].

Changes touching the token, URL handling, or network behavior also get a line in the pull request against the STRIDE table in `docs/SECURITY_MODEL.md`. See [[Security and Privacy]].

## What a complete change includes

- The code, with tests named by requirement ID, coverage at or above the floors (90% overall, 100% domain), and synthetic data only: never a real reading, token, or URL.
- Documentation updated: `README.md` content (its structure is fixed house style; do not add sections), `CHANGELOG.md` under Unreleased, `TODO.md`, `docs/OTS_SOFTWARE.md` if a dependency changed, and the relevant wiki page if the shape of the project changed.
- `demo.html` updated if user-facing behavior changed (the generator does this for display states).
- The full suite green: `python -m ruff check . && python -m ruff format --check . && python -m mypy && python -m pytest --cov && make -C firmware/xteink format-check test`.
- A Next Steps section in the pull request: a numbered list of what happens next, each step tagged HUMAN, AGENT, or AUTOMATED, with anything only a person can do (hardware, credentials, approvals) called out.

## Code style in brief

Python: ruff and strict mypy as configured in `pyproject.toml`, 99 columns, standard library only at runtime (a new runtime dependency needs an ADR-level conversation and an OTS entry). C++: clang-format on a Google base with the deviations in ADR-0007, no heap in `glucose_rules`. Swift: mirror the Python names and structure.

## Where to ask

Open an issue at https://github.com/esanacore/lightkeeper/issues for questions, bugs, and proposals. Security problems go through private vulnerability reporting, never a public issue; see [[Security and Privacy]]. Questions about Trio, Nightscout, or the devices belong in those communities, linked from [[Nightscout and Trio Setup]]. The maintainers cannot answer medical questions.

## Conduct

This project exists for a specific person's care and sits beside a community that has built these tools for years under the #WeAreNotWaiting banner. Be direct and kind. Review the change, not the person. Do not post anyone's health data, including your own. Therapy decisions belong to the person with diabetes and their care team, and "no" is a complete answer when a proposal would move the safety boundary. Contributions to dosing behavior are welcome, upstream, in Trio.

[[Roadmap]] lists where help is most useful right now.

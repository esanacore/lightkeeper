# Session Plan

This document records the current session's planned work before implementation begins. If this session is interrupted, the next agent or human can read this file to resume cleanly.

**This file is overwritten at the start of each session.** Before overwriting, make sure the previous session's outcomes are captured in `docs/AGENT_HANDOFF.md` or commit messages.

## Session

- **Date/Time**: 2026-10-18 07:20 UTC
- **Agent**: Claude
- **Previous Session**: Completed and pushed (repository created, CI green). Handoff in `docs/AGENT_HANDOFF.md`.

## Goal

Bring Lightkeeper to full compliance with Eric's Engineering Constitution 1.54.0 and add visuals and demos: an SVG display renderer, a generated display-state gallery, and a demo page driven by the shared vectors.

## Approach

1. Visuals: `render_svg`, `--svg` CLI option, `tools/gen_display_gallery.py`, drift tests (FR-011).
2. Declare FR-011 and update traceability.
3. Fix CI workflows: env check path and permissions, wiki workflow permissions, Dependabot pip entry.
4. Add lint, format, and type checking (ruff, mypy, clang-format) and fix what they find.
5. Fill template leftovers: wiki, CODEOWNERS, `.github/SECURITY.md`, `docs/HELP.md`, CONTRIBUTING links, devcontainer, `.python-version`, prerequisite check.
6. Security docs: data classification, retention, STRIDE threat model.
7. ADR index and promotion gatekeepers; OTS and TODO/CHANGELOG hygiene; remove `.constitution-bootstrap/`.
8. Prepare the 0.1.0 release in CHANGELOG; tagging and publishing wait for Eric's approval.
9. Run every constitution checker, push, confirm CI.

## Files Expected to Change

- `src/lightkeeper/**`, `tests/**`, `tools/gen_display_gallery.py`, `firmware/xteink/**`: create/modify
- `docs/**`, `wiki/**`, `README.md` (content only, house style kept), `CHANGELOG.md`, `TODO.md`: modify
- `.github/**`, `.devcontainer/devcontainer.json`, `.pre-commit-config.yaml`, `pyproject.toml`: modify
- `.constitution-bootstrap/`: delete

## Risks and Dependencies

- Release tag, GitHub Release, GitHub Pages, and constitution upstream fixes need Eric's approval.
- README structure is locked by Eric's house-style rule (`docs/MEMORY.md`); only content inside existing sections changes.

## Resumption Notes

- **Last completed step**: 9. All planned work done; release tag, Pages, and README layout wait on Eric (see `docs/AGENT_HANDOFF.md`).
- **Uncommitted changes**: none at time of writing.
- **Known issues**: none.

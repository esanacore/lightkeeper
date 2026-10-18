# Session Plan

This document records the current session's planned work before implementation begins. If this session is interrupted, the next agent or human can read this file to resume cleanly.

**This file is overwritten at the start of each session.** Before overwriting, make sure the previous session's outcomes are captured in `docs/AGENT_HANDOFF.md` or commit messages.

## Session

- **Date/Time**: 2026-10-18 19:30 UTC
- **Agent**: Claude
- **Previous Session**: Compliance push completed and pushed. Handoff in `docs/AGENT_HANDOFF.md`.

## Goal

Apply the two review reports (adversarial safety review, docs/product review), expand the wiki, and keep the professional polish pass going.

## Approach

1. Safety review: poisoned-entry isolation, watch-loop resilience, SVG stamp, duplicate tiebreak (Python); NaN/date bounds (firmware); crash-safe parsing, draft settings, foreground re-classification (iOS). Tests and a shared vector for each.
2. Docs review: Intended Use section, HAZ-008 note, threshold wording, hazard order, ADR index, reserved FR-013..015, ENV_VARS token note, HARDWARE heading, ROADMAP versioning claim, demo page restyle.
3. Wiki build-out (background agent) with `tests/test_wiki.py`.
4. Traceability, CHANGELOG, TODO, handoff; run every checker; push; confirm CI including the iOS workflow.

## Status

Steps 1, 2, and 4 done in this session; step 3 committed when the wiki agent reported. See `docs/AGENT_HANDOFF.md` for what is next.

## Files Expected to Change

- `src/lightkeeper/**`, `tests/**`, `firmware/xteink/**`, `apps/ios/**`, `spec/display_vectors.json`, `demo.html`, `docs/**`, `wiki/**`, `CHANGELOG.md`, `TODO.md`.

## Risks and Dependencies

- Release tag, GitHub Release, GitHub Pages, and constitution upstream fixes need Eric's approval.
- README structure is locked by Eric's house-style rule (`docs/MEMORY.md`); only content inside existing sections changes.

## Resumption Notes

- **Last completed step**: 9. All planned work done; release tag, Pages, and README layout wait on Eric (see `docs/AGENT_HANDOFF.md`).
- **Uncommitted changes**: none at time of writing.
- **Known issues**: none.

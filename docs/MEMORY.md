# Project Memory

This file contains durable memories, codebase learnings, user preferences, and key architectural decisions. AI agents read this file at the start of each session to align with past context, and update it (at the user's discretion) at the end of a session.

> [!IMPORTANT]
> **User Discretion**: Do not add or edit entries in this file without presenting them to the user for review. The user has absolute discretion over what memories are retained.

## User Preferences & Styling Choices

<!-- 
  Record the user's development preferences, styling decisions, and custom choices.
  Examples:
  - "User prefers TailwindCSS for styling, styled-components for theme overrides."
  - "User prefers HSL values for colors in stylesheets."
  - "Avoid verbose inline comments; document code using JSDoc type definitions."
-->

- README.md is the house style for this project (Eric, 2026-10-18): keep its structure, tone, and order exactly as in commit 57e192e. That means the opening paragraph, the Safety first callout, Current Capabilities, How It Fits Together (Mermaid diagram), Quick Start with collapsed per-platform blocks, Run, Test, Demo, Project Structure, Documentation, Contributing, License. On 2026-10-24 Eric approved three additions: a version line under the badge (update it each release), the How It Fits Together diagram as a top-down rendered image from `assets/diagrams/` with the Mermaid source in a collapsed block, and the published demo link in the Demo section. On 2026-10-27 Eric approved a fourth: the hero render of the bedside enclosure (`hardware/enclosure/renders/hero.png`) with a one-line caption at the top of Current Capabilities; keep it current when the enclosure is re-rendered. Update the content inside those sections when features change, as the constitution requires, but do not restructure, restyle, or add new top-level sections without asking Eric first. New docs and sub-READMEs (for example firmware/xteink/README.md) follow the same voice.

## Codebase Learnings & Gotchas

<!-- 
  Record critical codebase quirks, system anomalies, test runner behaviors, or API gotchas.
  Examples:
  - "Database port must be forwarded to localhost:5432 during integration tests."
  - "The mock auth service in test environment times out after 30 seconds."
  - "Ensure Git CRLF conversion is disabled when modifying binary images."
-->

- 

## Active Project Decisions

<!-- 
  Record major technical and architectural decisions approved by the user that govern current work.
  Examples:
  - "Approved using SQLite for local development and PostgreSQL for production."
  - "Adopted the Compliance Validation Triad to gate pull requests."
-->

- ADR-0007 accepted (Eric, 2026-10-24): firmware C++ uses clang-format on a Google base, but function names and enum values mirror the Python (`parse_entry`, `Level::Stale`), the column limit is 100, and `#pragma once` is fine. Do not rename toward strict Google style.
- ADR-0009 accepted (Eric, 2026-10-25): the readable Nightscout token goes in the `api-secret` request header on the v1 API, never in a URL. Every client (including future firmware) does the same; JWT bearer auth is the fallback only if Nightscout drops the header path.
- License confirmed (Eric, 2026-10-24): Apache-2.0. Trio and Nightscout are AGPL-3.0, but this repository only reads Nightscout over HTTP and vendors none of their code.
- gstack section in `CLAUDE.md` kept (Eric, 2026-10-24). Where gstack is missing (cloud sessions), run `bash constitution/scripts/setup-machine.sh` or work without it. 

# ADR-0001: Record Architecture Decisions

Status: Accepted

Date: 2026-10-17

## Relationships

- Extends: none
- Supersedes: none
- Related: constitution/ARCHITECTURE.md

## Context

This project mixes community software we don't control (Trio, Nightscout, Dexcom and Omnipod hardware) with code we write. Decisions about where the safety boundary sits, and why, need to survive memory and be reviewable by Kaitlin and anyone who joins later.

## Decision

Record every significant architecture or safety decision as a numbered ADR in `docs/adr/`, using the constitution template.

## Consequences

Decisions have a written trail. Changes to the safety boundary require a new ADR, which forces the conversation to happen before code exists.

## Alternatives Considered

Notes in the README or commit messages only. Rejected because they scatter the reasoning and are easy to lose.

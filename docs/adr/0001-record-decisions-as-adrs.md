# 0001 – Record decisions as ADRs

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

docshelf is meant to be maintained by more than one person. Prior art in this space
(document libraries for Wagtail and Django) mostly died with its single maintainer; the
reasoning behind design choices was lost with them.

## Decision

Architecture decisions are recorded as numbered ADRs in `docs/adr/`. ADRs are not rewritten;
a new ADR supersedes an old one.

## Alternatives

- Decisions in issues or PR descriptions only: hard to find, scattered.
- A single design document: loses the history of why things changed.

## Consequences

Changes to models, URLs, settings or supported frameworks need an ADR in the same PR.

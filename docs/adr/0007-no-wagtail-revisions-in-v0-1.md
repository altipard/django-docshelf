# 0007 – No Wagtail revisions or draft state for entries in v0.1

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

Wagtail offers revisions, drafts and scheduled publishing for snippets through
`RevisionMixin` and `DraftStateMixin`. Both must be inherited by the concrete model. The core
models live in `docshelf`, which must not depend on Wagtail (ADR-0002).

## Decision

v0.1 ships without revisions and draft state for entry metadata. An entry is published or
not (`is_published`); content history is covered by versions with validity dates.

## Alternatives

- **Swappable models** (`DOCSHELF_ENTRY_MODEL`, like `AUTH_USER_MODEL`): a Wagtail project
  uses a subclass with the mixins. Most flexible, but adds complexity to every query and
  migration before the base model is stable.
- **Separate concrete models in the Wagtail app:** two data models for the same thing,
  imports and docs split by framework.

## Consequences

- Editing an entry's title or category takes effect immediately and is only logged, not
  versioned.
- Swappable models remain the preferred path when revisions are needed; that needs a new ADR
  and should land before 1.0, since swapping later requires a data migration.

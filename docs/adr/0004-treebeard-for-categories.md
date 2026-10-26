# 0004 – django-treebeard for the category tree

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

Categories need ordering and optionally nesting. The closest prior art used django-mptt,
which is no longer actively maintained.

## Decision

Categories use django-treebeard (materialized path). Wagtail already depends on it, so Wagtail
projects get no new dependency.

## Alternatives

- **django-mptt:** unmaintained.
- **Flat categories with a parent foreign key:** no dependency, but tree queries and ordering
  must be written by hand.
- **Flat categories only:** enough for many sites, but nesting would need a migration later.

## Consequences

- The version range must stay compatible with Wagtail's pin (Wagtail 8.0 requires
  `django-treebeard<6`).

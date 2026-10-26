# 0002 – Django core with optional Wagtail integration, no django CMS

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

The first user is a Wagtail site, but the problem (catalogue, versions, stable links, access)
is not Wagtail-specific. Wagtail users look for `wagtail-*` packages; Django users without a
CMS have no option either. django CMS has related building blocks (django-filer,
djangocms-versioning), but djangocms-versioning requires django CMS itself.

## Decision

- One distribution `django-docshelf`, import name `docshelf`.
- `docshelf` is a plain Django app (models, admin, views, serving, access). It must not
  import Wagtail.
- `docshelf.contrib.wagtail` adds the Wagtail integration, installed via the extra
  `django-docshelf[wagtail]`.
- No django CMS integration is planned.
- Supported: Django 5.2 LTS, 6.0, 6.1; Wagtail 7.0 LTS, 8.0.

## Alternatives

- **Wagtail-only package** (`wagtail-docshelf`): simpler, but excludes plain Django and couples
  the data model to Wagtail's release cycle, which killed several predecessors.
- **Two distributions** (core and Wagtail adapter): cleaner dependency story, but doubles
  release work for a small project. Can be split later without changing import paths.
- **django CMS adapter:** dropped on request; no user for it.

## Consequences

- CI runs one environment without Wagtail to prove the core stays independent.
- Wagtail-specific model features (revisions, draft state) are not available on core models;
  see the open question in the concept.
- The name `wagtail-docshelf` may later be registered as an alias that depends on
  `django-docshelf[wagtail]`, for discoverability.

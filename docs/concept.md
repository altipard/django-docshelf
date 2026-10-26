# Concept

Status: draft for v0.1. Decisions referenced as ADR-NNNN live in [adr/](adr/).

## Problem

A typical "Documents" page on a club, association or company site:

- mixes uploaded files, links to other sites and online forms in free text,
- keeps "as of" dates by hand in the link text,
- loses the previous file when an editor replaces it (Wagtail deletes the old file and the
  URL changes with the file name),
- cannot tell public documents from members-only ones, or enforces it only in the page and
  not when the file is served.

No maintained Django or Wagtail package covers this. Wagtail RFC 112 plans file-level
history for documents and images, not a catalogue with validity and stable links.

## Goals

1. One catalogue for files, external links and forms, grouped by category, rendered uniformly.
2. Versions per entry with validity dates and a change note; the archive stays reachable.
3. A stable URL per entry that always resolves to the current version.
4. Access rules enforced when serving, not only when listing.
5. Plain Django core, optional Wagtail integration (ADR-0002).

## Non-goals for v0.1

- django CMS integration (ADR-0002)
- Wagtail's document library (`wagtaildocs`) as file source (ADR-0003, may come later; the
  import command copies files instead)
- Wagtail revisions and draft state for entry metadata (ADR-0007)
- Approval workflows, scheduled publishing beyond validity dates
- Download statistics, full-text search inside files, thumbnails
- Signed cloud storage URLs beyond what `Storage.url()` already provides

## Domain model

```
Category (tree)          1 ─── n  Entry           1 ─── n  Version
  name, slug                        title, slug               label
  description                       summary                   file   | url
  position                          kind                      valid_from
                                    audience                  valid_until
                                    groups (if audience=groups)
                                    issuer                    change_note
                                    review_due                created_at, created_by
                                    is_published
```

### Category

A tree (django-treebeard, ADR-0004) so sites can model "Club › Statutes & rules" or a flat
list. The category tree is site data, not code: the package ships no categories.

### Entry

The stable identity users link to. `slug` is unique and forms the permalink.

`kind` comes from a registry. Built-in kinds:

| Kind | Version target | Rendered as |
|---|---|---|
| `file` | uploaded file | "PDF · 118 KB" |
| `link` | external URL | "External ↗ example.org" |
| `form` | external URL | "Online form ↗" |

A kind declares whether its versions need a file or a URL, its label and icon. Projects can
register further kinds (for example "video" or "map").

`is_published` hides an entry entirely. Revisions and drafts of the entry metadata are out of
scope for v0.1 (ADR-0007); versions already carry the history of the content.

### Version

What an entry points to at a given time. A version has either a file or a URL, depending on
the kind. Link entries get history too: a moved form URL is a new version.

- **Immutable once published.** Corrections are a new version. Files are never overwritten
  (ADR-0003).
- `valid_from` (required), `valid_until` (optional), `change_note` (optional),
  `label` (free text, e.g. "Adopted by general assembly 2021-09-18").

### Computed status

Status is derived from dates, never stored, so it cannot go stale:

| Version status | Rule |
|---|---|
| scheduled | `valid_from` > today |
| current | the newest version with `valid_from` ≤ today and `valid_until` empty or ≥ today |
| superseded | older than the current version |
| expired | `valid_until` < today and no newer version is valid |

An entry without a current version is shown as "expired" or hidden (setting). `review_due`
on the entry feeds an admin reminder ("review overdue"), independent of validity.

## URLs

`include("docshelf.urls")` or, in Wagtail, a library page (see below):

| URL | Response |
|---|---|
| `/` | list grouped by category, client-side filter |
| `/<slug>/` | **permalink**: 302 to the current version (file URL below, or external URL) |
| `/<slug>/history/` | archive of all published versions with validity and change notes |
| `/<slug>/v/<version_id>/<filename>` | serves the file of one version |

The file URL contains the file name for readable downloads, but only `version_id` is used for
lookup, so renaming never breaks it. A JSON variant of the list is planned, not in v0.1.

## Access

`audience` per entry: `public`, `authenticated` or `groups`. The check runs in the list
(hidden or marked), on the permalink and on every file download.

Custom rules via `DOCSHELF_ACCESS_POLICY`, a class with
`can_view(user, entry) -> bool` and `filter_queryset(user, queryset)`. Anonymous users who
are denied are redirected to `settings.LOGIN_URL`; signed-in users get 403.

Access control is only effective when files are not reachable directly. Files therefore go to
a separate storage, by default outside `MEDIA_ROOT` (ADR-0003).

## Serving

`DOCSHELF_SERVE_BACKEND` selects how a permitted file is delivered:

| Backend | Use |
|---|---|
| `django` (default) | `FileResponse`, fine for low traffic |
| `x-accel` | nginx `X-Accel-Redirect` to an `internal` location |
| `x-sendfile` | Apache / lighttpd |
| `redirect` | 302 to `storage.url()`, e.g. signed S3 URLs |

## Wagtail integration (`docshelf.contrib.wagtail`)

- `SnippetViewSet` for entries (versions as inline panel) and categories, with list filters
  for category, kind, audience and "review overdue"
- `ChooserViewSet` for entries
- StreamField blocks: `EntryChooserBlock` (single card), `CategoryListBlock` (all entries of a
  category)
- Rich text link type `docshelf` that links to the permalink
- `LibraryPage` (`RoutablePageMixin`) that serves the URLs above below any page in the tree
- Search index for entries, reference index registration, admin log entries
- Dashboard panel "review overdue"

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `DOCSHELF_STORAGE` | `"docshelf"` alias, fallback `default` with a warning | storage for version files |
| `DOCSHELF_SERVE_BACKEND` | `"django"` | see Serving |
| `DOCSHELF_X_ACCEL_PREFIX` | `"/protected/docshelf/"` | internal nginx location |
| `DOCSHELF_ACCESS_POLICY` | `"docshelf.access.DefaultPolicy"` | see Access |
| `DOCSHELF_KINDS` | built-in kinds | registry extension |
| `DOCSHELF_SHOW_EXPIRED` | `False` | list entries without a current version |

## Import

`manage.py docshelf_import` brings existing documents into the catalogue. Sources:

- `csv`: one row per version (`entry_slug`, `title`, `category_path`, `kind`, `file` or `url`,
  `valid_from`, `valid_until`, `label`, `change_note`, `audience`). Rows with the same
  `entry_slug` become versions of one entry. Missing categories are created along the path
  (`Club/Statutes & rules`).
- `wagtaildocs` (only with the Wagtail integration): selected Wagtail documents by ID,
  collection or tag. The file is **copied** into docshelf storage; the Wagtail document stays
  untouched.

Behaviour:

- `--dry-run` prints what would happen, without writing.
- Idempotent: an entry is matched by slug, a version by entry and content hash of the file
  (or URL), so a second run creates nothing new.
- `--redirects FILE` writes a mapping old URL → permalink (CSV) for the project's redirect
  mechanism (`django.contrib.redirects`, `wagtail.contrib.redirects` or the web server). The
  command does not create redirects itself.

## Internationalisation

All strings translatable, English and German shipped from v0.1.

## Compatibility

Python 3.10–3.14, Django 5.2 LTS / 6.0 / 6.1, Wagtail 7.0 LTS / 8.0. Supported versions follow
the upstream support windows; a dropped version is a minor release.

## v0.1 scope

1. Models, migrations, Django admin
2. Kinds `file`, `link`, `form` with registry
3. Versions with validity, change note, immutability rules
4. Permalink, history, file serving with `django` and `x-accel` backends
5. Access: `public`, `authenticated`, `groups`, policy hook
6. List template with category grouping and client-side filter, overridable templates
7. Wagtail: snippets, chooser, blocks, rich text link, `LibraryPage`
8. Import command with `csv` and `wagtaildocs` sources
9. de/en translations, tests across the matrix, demo project, docs

## Later

- Wagtail documents as file source: a version references a `wagtaildocs` document instead of
  its own file. File access stays behind `Version.open()` and the serve backend so this is
  additive (ADR-0003).
- Revisions and drafts for entry metadata in Wagtail, probably via swappable models
  (ADR-0007).

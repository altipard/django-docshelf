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
register further kinds (for example "video" or "map") with `docshelf.kinds.register()` in
`AppConfig.ready()`. The model field uses callable choices, so new kinds need no migration.

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
(entries the user may not see are left out), on the permalink, the history and every file
download. Scheduled versions are never listed or served.

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

- Snippets for entries (versions as inline panel, `Entry` is a `ClusterableModel`) and
  categories, grouped under a "Documents" menu, with list filters for category, kind, audience
  and published state. The category form places the node in the tree (parent field).
- The snippet chooser picks entries and categories.
- StreamField blocks: `EntryBlock` (one card) and `CategoryBlock` (all entries of a category,
  optionally with subcategories). Both respect the access policy of the visitor.
- `LibraryPage` (`RoutablePageMixin`) serves list, permalink, history and files below a page.
  `root_category` limits a page to a subtree. Set
  `DOCSHELF_ROUTER = "docshelf.contrib.wagtail.routing.LibraryPageRouter"` so that
  `Entry.get_absolute_url()` points below the page; with several pages the most specific root
  category wins. Wagtail only routes slash-terminated paths without dots, so file URLs below a
  page are `/<slug>/v/<version_id>/`; the file name comes from `Content-Disposition`.
- Dashboard panel "Documents due for review" for users who may change entries.
- Snippet actions are logged by Wagtail; registered snippets take part in the reference index.

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `DOCSHELF_STORAGE` | `"docshelf"` alias, fallback `default` with a warning | storage for version files |
| `DOCSHELF_SERVE_BACKEND` | `"django"` | see Serving |
| `DOCSHELF_X_ACCEL_PREFIX` | `"/protected/docshelf/"` | internal nginx location |
| `DOCSHELF_ACCESS_POLICY` | `"docshelf.access.DefaultPolicy"` | see Access |
| `DOCSHELF_SHOW_EXPIRED` | `False` | list entries without a current version |
| `DOCSHELF_ROUTER` | `"docshelf.routing.NamespaceRouter"` | where entry URLs point, see Wagtail integration |

## Import

`manage.py docshelf_import` brings existing documents into the catalogue.

```bash
manage.py docshelf_import csv documents.csv [--base-dir DIR]
manage.py docshelf_import wagtaildocs --ids 13 14 --category "Club/Statutes"
manage.py docshelf_import wagtaildocs --collection "Club documents" --emit-csv docs.csv
```

- `csv`: one row per version with the columns `entry_slug`, `title`, `category_path`, `kind`,
  `file`, `url`, `valid_from`, `valid_until`, `label`, `change_note`, `audience`, `summary`,
  `issuer`, `old_url`. Rows with the same `entry_slug` become versions of one entry; entry
  fields are only read from the first row of a new entry. Missing categories are created
  along the path (`Club/Statutes & rules`). `file` is a path relative to the CSV or
  `wagtaildoc:<id>`.
- `wagtaildocs` (only with Wagtail): one entry per selected document (`--ids`, `--collection`,
  `--tag`). The file is **copied** into docshelf storage; the Wagtail document stays untouched.
  `--emit-csv` writes the rows instead of importing them, so they can be edited first (merge
  documents into versions of one entry, set categories and dates) and imported with `csv`.

Behaviour:

- Two phases: every row is validated before anything is written. One invalid row aborts the
  whole import, no categories, entries or files are created.
- `--dry-run` runs the validation only.
- Idempotent: an entry is matched by slug, a version by entry and SHA-256 of the file (or URL),
  so a second run creates nothing. Existing entries get new versions, their fields are not
  changed.
- `--redirects FILE` writes `old_url,new_url` pairs (old URL from the `old_url` column, for
  Wagtail documents their serve URL) for the project's redirect mechanism. The command does not
  create redirects itself.

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
7. Wagtail: snippets, chooser, blocks, `LibraryPage`, dashboard panel
8. Import command with `csv` and `wagtaildocs` sources
9. de/en translations, tests across the matrix, demo project, docs

## Later

- Wagtail documents as file source: a version references a `wagtaildocs` document instead of
  its own file. File access stays behind `Version.open()` and the serve backend so this is
  additive (ADR-0003).
- Revisions and drafts for entry metadata in Wagtail, probably via swappable models
  (ADR-0007).
- Rich text link type for entries. Needs a Draftail plugin (JavaScript); until then editors
  link the permalink as an ordinary link.
- Wagtail search index for entries. The core model cannot inherit `index.Indexed` without
  depending on Wagtail; needs the same solution as revisions.

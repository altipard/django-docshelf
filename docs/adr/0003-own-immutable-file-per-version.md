# 0003 – Own immutable file per version instead of Wagtail documents

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

Versions need their own file that survives later uploads. Wagtail's document model
(`wagtaildocs.Document`) has one file per document; "replace file" deletes the old file, and
the serve URL contains the file name, so links break when the name changes. Files under
`MEDIA_ROOT` are often served by the web server directly, which bypasses any access check.

Wagtail RFC 112 discusses file-level versioning with the file content as an immutable blob
and versioned metadata. It is unfunded and does not cover catalogues or validity.

## Decision

- Each `Version` stores its own file in a dedicated storage (`DOCSHELF_STORAGE`), by default
  outside `MEDIA_ROOT`.
- A file is never overwritten or edited after the version is published; a correction is a new
  version.
- All file access goes through `Version.open()` and the serve backend, so another file source
  can be added later without changing URLs.

## Alternatives

- **Foreign key to `wagtaildocs.Document`:** files appear in Wagtail's document library, but
  ties the core to Wagtail, inherits the replace-file behaviour and the public `MEDIA_ROOT`.
- **Custom Wagtail document model** (`WAGTAILDOCS_DOCUMENT_MODEL`): project-wide swap, hard to
  introduce into existing projects, still Wagtail-only.
- **django-filer:** second media library in Wagtail projects; its canonical URL changes with
  each upload.

## Consequences

- Files are not visible in Wagtail's document library; the Wagtail integration provides its
  own chooser and link type.
- Deployments must provide the storage (and, for `x-accel`, an internal nginx location).
- Storage grows with every version; a retention setting may follow.

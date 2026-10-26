# 0006 – Conventional Commits and commitizen, no publishing yet

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

Release versions should follow from the changes, not from manual decisions. The package is
pre-alpha and must not be published to PyPI yet.

## Decision

- Conventional Commits are required and checked by commitizen (pre-commit hook and CI on pull
  requests). `fix` → patch, `feat` → minor, `!`/`BREAKING CHANGE` → major; other types do not
  release.
- The version lives only in Git tags (`version_provider = "scm"`, tags without `v`), read at
  build time by hatch-vcs. `major_version_zero` keeps breaking changes in 0.x.
- No release or publishing workflow until v0.1 is ready. Installation is from source
  (`pip install -e`).

## Alternatives

- **Manual versioning in `pyproject.toml`:** easy to forget, no link to the changes.
- **semantic-release:** Node tooling in a Python project.

## Consequences

- When publishing is wanted: a release workflow on `main` (commitizen bump, tag, GitHub
  release, PyPI trusted publishing), recorded in a new ADR.

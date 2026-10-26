# Contributing

## Setup

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest
```

Run the full matrix locally with `uvx tox`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/), checked by commitizen.
The type decides the release: `fix` → patch, `feat` → minor, `!` or `BREAKING CHANGE` → major.
All other types (`docs`, `chore`, `ci`, `test`, `refactor`, `style`, `build`) do not release.

- Subject in imperative mood, describes the behaviour, not the files.
- Body only when needed: why, rejected alternatives, side effects.
- One logical change per commit.

## Decisions

Architecture decisions are recorded in [docs/adr/](docs/adr/). ADRs are not rewritten;
a new ADR supersedes an old one.

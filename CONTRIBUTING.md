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

## Translations

English and German ship with the package; CI fails when a string has no German translation.
After changing translatable strings (needs gettext):

```bash
cd src/docshelf
export PYTHONPATH=../.. DJANGO_SETTINGS_MODULE=tests.settings
uv run django-admin makemessages -l de --ignore "migrations/*" --no-obsolete
# translate the new entries in locale/de/LC_MESSAGES/django.po
uv run django-admin compilemessages
```

Commit both `django.po` and `django.mo`.

## Decisions

Architecture decisions are recorded in [docs/adr/](docs/adr/). ADRs are not rewritten;
a new ADR supersedes an old one.

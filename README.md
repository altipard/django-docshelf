# django-docshelf

A document library for Django and Wagtail.

> **Status: pre-alpha.** Concept stage, nothing is released yet. See [docs/concept.md](docs/concept.md).

Many sites have a "Documents" or "Downloads" page that grows into a mix of uploaded PDFs,
links to other sites and online forms, with "as of" dates maintained by hand. Replacing a
file breaks links or silently drops the previous version.

docshelf models that page as a catalogue:

- **Entries** in a category tree. An entry is a file, an external link or an online form,
  rendered the same way.
- **Versions** per entry with validity dates and a change note. Old versions stay available
  as an archive.
- **Stable URLs**: `/<slug>/` always resolves to the current version.
- **Audiences**: public, signed-in users or selected groups, enforced when the file is served.
- **Wagtail integration** (optional): snippets, StreamField blocks, a library page and a
  dashboard panel for documents due for review.

## Installation (local development only)

```bash
git clone git@github.com:altipard/django-docshelf.git
cd django-docshelf
uv sync
uv run pytest
```

In a project:

```bash
pip install -e ../django-docshelf            # Django only
pip install -e "../django-docshelf[wagtail]" # with Wagtail integration
```

```python
INSTALLED_APPS = [
    # ...
    "docshelf",
    "docshelf.contrib.wagtail",  # Wagtail projects only
]
```

```python
# urls.py
urlpatterns = [
    path("documents/", include("docshelf.urls")),
]

# settings.py: keep files out of MEDIA_ROOT so access rules cannot be bypassed
STORAGES = {
    # ...
    "docshelf": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": BASE_DIR / "private-media" / "docshelf"},
    },
}
DOCSHELF_SERVE_BACKEND = "x-accel"  # default "django"
```

With `x-accel`, nginx delivers the file after Django has checked access:

```nginx
location /protected/docshelf/ {
    internal;
    alias /srv/app/private-media/docshelf/;
}
```

Override `docshelf/base.html` to render the pages inside the site layout.

### Wagtail

```python
INSTALLED_APPS += ["docshelf", "docshelf.contrib.wagtail"]
DOCSHELF_ROUTER = "docshelf.contrib.wagtail.routing.LibraryPageRouter"
```

Create a "Document library" page in the page tree; entries are managed under
**Documents** in the Wagtail admin. `docshelf.contrib.wagtail.blocks.EntryBlock` and
`CategoryBlock` place single documents or whole categories in any StreamField.

## Compatibility

| | Versions |
|---|---|
| Python | 3.10 – 3.14 |
| Django | 5.2 LTS, 6.0, 6.1 |
| Wagtail | 7.0 LTS, 8.0 |

## Documentation

- [Demo site](demo/README.md)
- [Concept](docs/concept.md)
- [Architecture decisions](docs/adr/)
- [Contributing](CONTRIBUTING.md)

## License

BSD-3-Clause, see [LICENSE](LICENSE).

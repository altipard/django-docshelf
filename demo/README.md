# docshelf demo

A small Wagtail site with sample data: categories, a statute with two versions, a form, an
external link, members-only minutes and an entry due for review.

```bash
# from the repository root
uv sync --extra wagtail
uv run python demo/manage.py migrate
uv run python demo/manage.py seed_demo
uv run python demo/manage.py runserver
```

- Library: http://localhost:8000/documents/ (set the browser language to German to see the
  German translation)
- Wagtail admin: http://localhost:8000/admin/ (user `admin`, password `admin`), menu
  **Documents**
- Django admin: http://localhost:8000/django-admin/

`seed_demo` deletes all docshelf data and library pages before creating the samples.

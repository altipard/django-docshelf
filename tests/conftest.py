import datetime

import pytest
from django.core.files.base import ContentFile

from docshelf.models import Category, Entry, Version


@pytest.fixture
def category(db):
    return Category.add_root(name="Club", slug="club")


@pytest.fixture
def file_entry(category):
    return Entry.objects.create(title="Statutes", slug="statutes", category=category, kind="file")


@pytest.fixture
def link_entry(category):
    return Entry.objects.create(
        title="Membership application", slug="membership", category=category, kind="form"
    )


@pytest.fixture
def make_version():
    def make(entry, valid_from, content=b"%PDF-1.7", name="doc.pdf", **kwargs):
        version = Version(entry=entry, valid_from=valid_from, **kwargs)
        if entry.kind_obj.needs_file and "url" not in kwargs:
            version.file = ContentFile(content, name=name)
        version.full_clean()
        version.save()
        return version

    return make


@pytest.fixture
def day():
    return datetime.date(2026, 10, 26)

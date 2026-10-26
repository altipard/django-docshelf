from datetime import date

import pytest
from django.utils import translation

from docshelf.status import EntryStatus

pytestmark = pytest.mark.django_db


def test_german_catalogue_is_shipped(client, file_entry, make_version):
    make_version(file_entry, date(2024, 1, 15))
    with translation.override("de"):
        assert str(EntryStatus.CURRENT.label) == "Aktuell"
        content = client.get("/documents/").content.decode()
    assert "Stand" in content
    assert "Fassungen" in content

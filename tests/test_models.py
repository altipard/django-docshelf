import hashlib
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError

from docshelf.models import Category, Entry, Version
from docshelf.status import EntryStatus
from docshelf.storage import get_storage

pytestmark = pytest.mark.django_db


def test_category_tree(category):
    child = category.add_child(name="Statutes & rules", slug="statutes-rules")
    assert child.get_parent() == category
    assert list(Category.get_root_nodes()) == [category]


def test_file_version_stores_checksum_size_and_unique_path(file_entry, make_version):
    first = make_version(file_entry, date(2021, 9, 18), content=b"v1")
    second = make_version(file_entry, date(2024, 1, 15), content=b"v2")
    assert first.checksum == hashlib.sha256(b"v1").hexdigest()
    assert first.size == 2
    assert first.filename == second.filename == "doc.pdf"
    assert first.file.name != second.file.name
    assert first.file.storage is get_storage()


def test_entry_current_version_and_status(file_entry, make_version, day):
    make_version(file_entry, date(2021, 9, 18))
    newest = make_version(file_entry, date(2024, 1, 15))
    entry = Entry.objects.with_versions().get(pk=file_entry.pk)
    assert entry.current_version(day) == newest
    assert entry.status(day) == EntryStatus.CURRENT


def test_file_kind_requires_file(file_entry):
    version = Version(entry=file_entry, valid_from=date(2024, 1, 1))
    with pytest.raises(ValidationError) as exc:
        version.full_clean()
    assert "file" in exc.value.message_dict


def test_url_kind_requires_url_and_rejects_file(link_entry):
    with pytest.raises(ValidationError) as exc:
        Version(entry=link_entry, valid_from=date(2024, 1, 1)).full_clean()
    assert "url" in exc.value.message_dict

    version = Version(
        entry=link_entry,
        valid_from=date(2024, 1, 1),
        file=ContentFile(b"x", name="x.pdf"),
    )
    with pytest.raises(ValidationError) as exc:
        version.full_clean()
    assert "file" in exc.value.message_dict


def test_url_version_checksum(link_entry, make_version):
    version = make_version(link_entry, date(2024, 1, 1), url="https://forms.example.org/a")
    assert version.checksum == hashlib.sha256(b"https://forms.example.org/a").hexdigest()
    assert version.size is None


def test_valid_until_before_valid_from_is_rejected(link_entry):
    version = Version(
        entry=link_entry,
        url="https://example.org",
        valid_from=date(2024, 1, 2),
        valid_until=date(2024, 1, 1),
    )
    with pytest.raises(ValidationError) as exc:
        version.full_clean()
    assert "valid_until" in exc.value.message_dict


def test_database_rejects_invalid_range(link_entry):
    with pytest.raises(IntegrityError):
        Version.objects.create(
            entry=link_entry,
            url="https://example.org",
            valid_from=date(2024, 1, 2),
            valid_until=date(2024, 1, 1),
        )


def test_target_of_existing_version_is_immutable(link_entry, make_version):
    version = make_version(link_entry, date(2024, 1, 1), url="https://example.org/old")
    version = Version.objects.get(pk=version.pk)
    version.url = "https://example.org/new"
    with pytest.raises(ValidationError):
        version.full_clean()
    with pytest.raises(ValueError):
        version.save()


def test_metadata_of_existing_version_is_editable(file_entry, make_version):
    version = Version.objects.get(pk=make_version(file_entry, date(2024, 1, 1)).pk)
    version.change_note = "Typo in label fixed"
    version.valid_until = date(2025, 1, 1)
    version.full_clean()
    version.save()


def test_kind_change_to_other_target_is_rejected_with_versions(file_entry, make_version):
    make_version(file_entry, date(2024, 1, 1))
    file_entry.kind = "link"
    with pytest.raises(ValidationError) as exc:
        file_entry.full_clean()
    assert "kind" in exc.value.message_dict


def test_kind_change_with_same_target_is_allowed(link_entry, make_version):
    make_version(link_entry, date(2024, 1, 1), url="https://example.org")
    link_entry.kind = "link"
    link_entry.full_clean()


def test_unknown_kind_is_rejected(category):
    entry = Entry(title="X", slug="x", category=category, kind="nope")
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "kind" in exc.value.message_dict


def test_deleting_version_deletes_file(
    file_entry, make_version, django_capture_on_commit_callbacks
):
    version = make_version(file_entry, date(2024, 1, 1))
    storage, name = version.file.storage, version.file.name
    assert storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        version.delete()
    assert not storage.exists(name)


def test_category_with_entries_cannot_be_deleted(file_entry):
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        file_entry.category.delete()

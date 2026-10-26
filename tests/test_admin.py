from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from docshelf.models import Entry, Version

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(admin_client):
    return admin_client


def test_changelists_render(staff, file_entry, make_version):
    make_version(file_entry, date(2024, 1, 1))
    for name in ("entry", "category"):
        response = staff.get(reverse(f"admin:docshelf_{name}_changelist"))
        assert response.status_code == 200
    response = staff.get(reverse("admin:docshelf_entry_changelist"), {"review": "overdue"})
    assert response.status_code == 200


def test_change_form_disables_target_of_saved_versions(staff, file_entry, make_version):
    make_version(file_entry, date(2024, 1, 1))
    response = staff.get(reverse("admin:docshelf_entry_change", args=[file_entry.pk]))
    assert response.status_code == 200
    form = response.context["inline_admin_formsets"][0].formset.forms[0]
    assert form.fields["file"].disabled
    assert form.fields["url"].disabled


def test_add_entry_with_version_sets_created_by(staff, category, admin_user):
    data = {
        "title": "Statutes",
        "slug": "statutes",
        "category": category.pk,
        "kind": "file",
        "sort_order": 0,
        "audience": "public",
        "is_published": "on",
        "versions-TOTAL_FORMS": 1,
        "versions-INITIAL_FORMS": 0,
        "versions-0-label": "2021",
        "versions-0-file": SimpleUploadedFile("statutes.pdf", b"%PDF"),
        "versions-0-valid_from": "2021-09-18",
    }
    response = staff.post(reverse("admin:docshelf_entry_add"), data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    version = Version.objects.get(entry=Entry.objects.get(slug="statutes"))
    assert version.created_by == admin_user
    assert version.filename == "statutes.pdf"

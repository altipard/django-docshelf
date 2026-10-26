from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from docshelf.models import Audience, Entry

pytestmark = pytest.mark.django_db

PAST = date(2021, 9, 18)


def body(response):
    return b"".join(response.streaming_content)


@pytest.fixture
def statutes(file_entry, make_version):
    make_version(file_entry, PAST, content=b"old", name="statutes.pdf")
    current = make_version(file_entry, date(2024, 1, 15), content=b"new", name="statutes.pdf")
    return file_entry, current


def test_list_groups_entries_by_category(client, statutes, link_entry, make_version):
    make_version(link_entry, PAST, url="https://forms.example.org/apply")
    child = statutes[0].category.add_child(name="Forms", slug="forms")
    link_entry.category = child
    link_entry.save()

    response = client.get("/documents/")
    assert response.status_code == 200
    sections = response.context["sections"]
    assert [(c.slug, [e.slug for e in entries]) for c, entries in sections] == [
        ("club", ["statutes"]),
        ("forms", ["membership"]),
    ]
    content = response.content.decode()
    assert "PDF · 3" in content
    assert "forms.example.org" in content


def test_list_hides_entries_without_current_version(client, file_entry, make_version):
    make_version(file_entry, PAST, valid_until=date(2022, 1, 1))
    assert client.get("/documents/").context["sections"] == []


def test_list_shows_expired_entries_when_enabled(client, settings, file_entry, make_version):
    settings.DOCSHELF_SHOW_EXPIRED = True
    make_version(file_entry, PAST, valid_until=date(2022, 1, 1))
    response = client.get("/documents/")
    assert [e.slug for _, entries in response.context["sections"] for e in entries] == ["statutes"]
    assert "No longer valid" in response.content.decode()


def test_permalink_redirects_to_current_file(client, statutes):
    entry, current = statutes
    response = client.get(f"/documents/{entry.slug}/")
    assert response.status_code == 302
    assert response["Location"] == f"/documents/statutes/v/{current.pk}/statutes.pdf"
    assert response["Cache-Control"] == "no-cache"


def test_permalink_redirects_link_kind_to_url(client, link_entry, make_version):
    make_version(link_entry, PAST, url="https://forms.example.org/apply")
    response = client.get("/documents/membership/")
    assert response["Location"] == "https://forms.example.org/apply"


def test_permalink_404_without_current_version_or_unpublished(client, file_entry, make_version):
    assert client.get("/documents/statutes/").status_code == 404
    make_version(file_entry, PAST)
    Entry.objects.filter(pk=file_entry.pk).update(is_published=False)
    assert client.get("/documents/statutes/").status_code == 404


def test_file_is_served_with_headers(client, statutes):
    entry, current = statutes
    response = client.get(current.get_file_url())
    assert response.status_code == 200
    assert body(response) == b"new"
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'inline; filename="statutes.pdf"'
    assert "immutable" in response["Cache-Control"]


def test_old_version_stays_reachable_and_filename_is_cosmetic(client, statutes):
    entry, current = statutes
    old = entry.versions.exclude(pk=current.pk).get()
    response = client.get(f"/documents/statutes/v/{old.pk}/renamed.pdf")
    assert body(response) == b"old"


def test_scheduled_version_is_not_served(client, file_entry, make_version):
    future = make_version(file_entry, timezone.localdate() + timedelta(days=30))
    assert client.get(future.get_file_url()).status_code == 404


def test_version_of_other_entry_is_not_served(client, statutes, category, make_version):
    other = Entry.objects.create(title="Rules", slug="rules", category=category, kind="file")
    version = make_version(other, PAST)
    assert client.get(f"/documents/statutes/v/{version.pk}/x.pdf").status_code == 404


def test_restricted_entry(client, django_user_model, statutes):
    entry, current = statutes
    members = Group.objects.create(name="Members")
    entry.audience = Audience.GROUPS
    entry.save()
    entry.groups.add(members)

    response = client.get(current.get_file_url())
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/?next=")
    assert client.get("/documents/").context["sections"] == []

    user = django_user_model.objects.create_user("guest")
    client.force_login(user)
    assert client.get(current.get_file_url()).status_code == 403

    user.groups.add(members)
    response = client.get(current.get_file_url())
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-cache"


def test_history_lists_versions_without_scheduled(client, statutes, make_version):
    entry, current = statutes
    make_version(entry, timezone.localdate() + timedelta(days=30), label="Next year")
    response = client.get("/documents/statutes/history/")
    statuses = [status for _, status in response.context["rows"]]
    assert sorted(statuses) == ["current", "superseded"]
    assert "Next year" not in response.content.decode()


def test_x_accel_backend(client, settings, statutes):
    settings.DOCSHELF_SERVE_BACKEND = "x-accel"
    entry, current = statutes
    response = client.get(current.get_file_url())
    assert response["X-Accel-Redirect"] == "/protected/docshelf/" + current.file.name
    assert response.content == b""


def test_redirect_backend(client, settings, statutes):
    settings.DOCSHELF_SERVE_BACKEND = "redirect"
    entry, current = statutes
    response = client.get(current.get_file_url())
    assert response.status_code == 302
    assert response["Location"] == current.file.url

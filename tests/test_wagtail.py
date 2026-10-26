from datetime import date, timedelta

import pytest

pytest.importorskip("wagtail")

from django.contrib.auth.models import AnonymousUser, Group  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import RequestFactory  # noqa: E402
from django.urls import reverse  # noqa: E402
from wagtail.models import Page  # noqa: E402

from docshelf.contrib.wagtail import routing  # noqa: E402
from docshelf.contrib.wagtail.blocks import CategoryBlock, EntryBlock  # noqa: E402
from docshelf.contrib.wagtail.models import LibraryPage  # noqa: E402
from docshelf.models import Audience, Category, Entry, Version  # noqa: E402

pytestmark = pytest.mark.django_db

PAST = date(2021, 9, 18)


@pytest.fixture(autouse=True)
def _clear_router_cache():
    routing.clear_cache()
    yield
    routing.clear_cache()


@pytest.fixture
def home():
    return Page.objects.get(depth=2)


@pytest.fixture
def library(home, settings):
    settings.DOCSHELF_ROUTER = "docshelf.contrib.wagtail.routing.LibraryPageRouter"
    return home.add_child(instance=LibraryPage(title="Library", slug="library"))


@pytest.fixture
def statutes(file_entry, make_version):
    version = make_version(file_entry, PAST, content=b"pdf", name="statutes.pdf")
    return file_entry, version


def body(response):
    return b"".join(response.streaming_content)


class TestCategorySnippet:
    def post(self, client, url, **data):
        payload = {"name": "", "slug": "", "parent": "", "description": ""}
        payload.update(data)
        return client.post(url, payload)

    def test_create_root_and_child_then_move_to_root(self, admin_client):
        add = reverse("wagtailsnippets_docshelf_category:add")
        assert self.post(admin_client, add, name="Club", slug="club").status_code == 302
        club = Category.objects.get(slug="club")
        assert club.is_root()

        self.post(admin_client, add, name="Forms", slug="forms", parent=club.pk)
        forms = Category.objects.get(slug="forms")
        assert forms.get_parent() == club

        edit = reverse("wagtailsnippets_docshelf_category:edit", args=[forms.pk])
        assert self.post(admin_client, edit, name="Forms", slug="forms").status_code == 302
        forms.refresh_from_db()
        assert forms.is_root()

    def test_listing(self, admin_client, category):
        response = admin_client.get(reverse("wagtailsnippets_docshelf_category:list"))
        assert response.status_code == 200
        assert "Club" in response.content.decode()


class TestEntrySnippet:
    def test_add_entry_with_version(self, admin_client, admin_user, category):
        data = {
            "title": "Statutes",
            "slug": "statutes",
            "summary": "",
            "category": category.pk,
            "kind": "file",
            "sort_order": 0,
            "is_published": "on",
            "audience": "public",
            "issuer": "",
            "review_due": "",
            "versions-TOTAL_FORMS": 1,
            "versions-INITIAL_FORMS": 0,
            "versions-MIN_NUM_FORMS": 0,
            "versions-MAX_NUM_FORMS": 1000,
            "versions-0-id": "",
            "versions-0-DELETE": "",
            "versions-0-label": "2021",
            "versions-0-file": SimpleUploadedFile("statutes.pdf", b"%PDF"),
            "versions-0-url": "",
            "versions-0-valid_from": "2021-09-18",
            "versions-0-valid_until": "",
            "versions-0-change_note": "",
        }
        response = admin_client.post(reverse("wagtailsnippets_docshelf_entry:add"), data)
        assert response.status_code == 302, response.context["form"].errors
        version = Version.objects.get(entry__slug="statutes")
        assert version.created_by == admin_user
        assert version.filename == "statutes.pdf"

    def test_edit_form_disables_target_of_saved_versions(self, admin_client, statutes):
        entry, _ = statutes
        url = reverse("wagtailsnippets_docshelf_entry:edit", args=[entry.pk])
        response = admin_client.get(url)
        assert response.status_code == 200
        version_form = response.context["form"].formsets["versions"].forms[0]
        assert version_form.fields["file"].disabled
        assert version_form.fields["url"].disabled

    def test_listing_with_filters(self, admin_client, statutes):
        url = reverse("wagtailsnippets_docshelf_entry:list")
        response = admin_client.get(url, {"kind": "file"})
        assert response.status_code == 200
        assert "Statutes" in response.content.decode()


class TestLibraryPage:
    def test_lists_entries_and_routes_below_page(self, client, library, statutes):
        entry, version = statutes
        response = client.get(library.url)
        assert response.status_code == 200
        assert "Statutes" in response.content.decode()

        assert entry.get_absolute_url() == "/library/statutes/"
        response = client.get(entry.get_absolute_url())
        assert response["Location"] == f"/library/statutes/v/{version.pk}/"
        response = client.get(response["Location"])
        assert body(response) == b"pdf"
        assert response["Content-Disposition"] == 'inline; filename="statutes.pdf"'
        assert client.get("/library/statutes/history/").status_code == 200

    def test_restricted_entry_redirects_to_login(self, client, library, statutes):
        entry, _ = statutes
        entry.audience = Audience.GROUPS
        entry.save()
        response = client.get("/library/statutes/")
        assert response.status_code == 302
        assert response["Location"].startswith("/accounts/login/")

    def test_root_category_limits_list_and_picks_page(
        self, client, home, library, statutes, category
    ):
        forms = category.add_child(name="Forms", slug="forms")
        entry = Entry.objects.create(title="Apply", slug="apply", category=forms, kind="form")
        Version.objects.create(entry=entry, url="https://forms.example.org", valid_from=PAST)
        forms_page = home.add_child(
            instance=LibraryPage(title="Forms", slug="forms", root_category=forms)
        )
        assert entry.get_absolute_url() == "/forms/apply/"
        assert statutes[0].get_absolute_url() == "/library/statutes/"

        sections = client.get(forms_page.url).context["sections"]
        assert [e.slug for _, entries in sections for e in entries] == ["apply"]


class TestBlocks:
    def render(self, block, value):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        return block.render(value, context={"request": request})

    def test_entry_block_renders_visible_entry_only(self, library, statutes):
        entry, _ = statutes
        assert "Statutes" in self.render(EntryBlock(), entry)

        entry.audience = Audience.GROUPS
        entry.save()
        entry.groups.add(Group.objects.create(name="Members"))
        assert self.render(EntryBlock(), entry).strip() == ""

    def test_category_block_without_filter(self, library, statutes, category):
        block = CategoryBlock()
        value = block.to_python({"category": category.pk, "include_subcategories": True})
        html = self.render(block, value)
        assert "Statutes" in html
        assert "docshelf-filter" not in html


def test_dashboard_lists_overdue_entries(admin_client, file_entry):
    file_entry.review_due = date.today() - timedelta(days=1)
    file_entry.save()
    content = admin_client.get(reverse("wagtailadmin_home")).content.decode()
    assert "Documents due for review" in content
    assert "Statutes" in content

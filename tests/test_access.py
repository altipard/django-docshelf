import pytest
from django.contrib.auth.models import AnonymousUser, Group

from docshelf.access import DefaultPolicy
from docshelf.models import Audience, Entry

pytestmark = pytest.mark.django_db


@pytest.fixture
def members():
    return Group.objects.create(name="Members")


@pytest.fixture
def entries(category, members):
    def make(slug, audience, **kwargs):
        return Entry.objects.create(
            title=slug, slug=slug, category=category, kind="file", audience=audience, **kwargs
        )

    group_entry = make("minutes", Audience.GROUPS)
    group_entry.groups.add(members)
    return {
        "public": make("statutes", Audience.PUBLIC),
        "authenticated": make("handbook", Audience.AUTHENTICATED),
        "groups": group_entry,
        "unpublished": make("draft", Audience.PUBLIC, is_published=False),
    }


def visible(user):
    return set(
        DefaultPolicy().filter_queryset(user, Entry.objects.all()).values_list("slug", flat=True)
    )


def test_anonymous_sees_public_only(entries):
    user = AnonymousUser()
    assert visible(user) == {"statutes"}
    assert DefaultPolicy().can_view(user, entries["public"])
    assert not DefaultPolicy().can_view(user, entries["authenticated"])


def test_signed_in_user_without_group(entries, django_user_model):
    user = django_user_model.objects.create_user("guest")
    assert visible(user) == {"statutes", "handbook"}
    assert not DefaultPolicy().can_view(user, entries["groups"])


def test_group_member(entries, members, django_user_model):
    user = django_user_model.objects.create_user("member")
    user.groups.add(members)
    assert visible(user) == {"statutes", "handbook", "minutes"}
    assert DefaultPolicy().can_view(user, entries["groups"])


def test_superuser_sees_all_published(entries, admin_user):
    assert visible(admin_user) == {"statutes", "handbook", "minutes"}
    assert not DefaultPolicy().can_view(admin_user, entries["unpublished"])

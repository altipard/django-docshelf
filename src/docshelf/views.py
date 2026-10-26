"""Public views and the building blocks they share with the Wagtail ``LibraryPage``."""

from collections import defaultdict
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .access import get_policy
from .conf import get_setting
from .models import Audience, Category, Entry
from .serving import serve
from .status import EntryStatus, VersionStatus, version_statuses


class LoginRequired(Exception):
    """Raised for anonymous users who may see an entry after signing in."""


def login_on_denied(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        request = next(a for a in args if hasattr(a, "user"))
        try:
            return view(*args, **kwargs)
        except LoginRequired:
            return redirect_to_login(request.get_full_path())

    return wrapper


def get_visible_entry(request, slug):
    entry = get_object_or_404(Entry.objects.with_versions(), slug=slug, is_published=True)
    if get_policy().can_view(request.user, entry):
        return entry
    if not request.user.is_authenticated:
        raise LoginRequired
    raise PermissionDenied


def build_sections(user, root=None, include_descendants=True, day=None):
    """Visible entries grouped by category in tree order: ``[(category, [entry, ...]), ...]``.

    Each entry gets ``current`` (version valid on ``day``) and ``current_status``.
    """
    day = day or timezone.localdate()
    show_expired = get_setting("SHOW_EXPIRED")
    entries = Entry.objects.select_related("category").with_versions()
    if root is not None:
        if include_descendants:
            entries = entries.filter(category__path__startswith=root.path)
        else:
            entries = entries.filter(category=root)
    by_category = defaultdict(list)
    for entry in get_policy().filter_queryset(user, entries):
        entry.current = entry.current_version(day)
        entry.current_status = entry.status(day)
        if entry.current is None and not (
            show_expired and entry.current_status == EntryStatus.EXPIRED
        ):
            continue
        by_category[entry.category_id].append(entry)
    categories = Category.get_tree(root) if root is not None else Category.get_tree()
    return [(c, by_category[c.pk]) for c in categories if c.pk in by_category]


def permalink_response(entry):
    version = entry.current_version()
    if version is None:
        raise Http404("No current version")
    target = version.get_file_url() if entry.kind_obj.needs_file else version.url
    response = HttpResponseRedirect(target)
    response["Cache-Control"] = "no-cache"
    return response


def history_rows(entry, day=None):
    statuses = version_statuses(entry.versions.all(), day or timezone.localdate())
    return [(v, s) for v, s in statuses.items() if s != VersionStatus.SCHEDULED]


def version_file_response(request, entry, version_id):
    """Only the id is used for the lookup, the file name in the URL is cosmetic."""
    version = next((v for v in entry.versions.all() if v.pk == version_id), None)
    if (
        version is None
        or not version.file
        or not entry.kind_obj.needs_file
        or version.valid_from > timezone.localdate()
    ):
        raise Http404("No such file")
    return serve(request, version, public=entry.audience == Audience.PUBLIC)


def entry_list(request):
    sections = build_sections(request.user)
    return render(request, "docshelf/entry_list.html", {"sections": sections})


@login_on_denied
def permalink(request, slug):
    """Stable URL of an entry, redirects to whatever version is current today."""
    return permalink_response(get_visible_entry(request, slug))


@login_on_denied
def history(request, slug):
    entry = get_visible_entry(request, slug)
    context = {"entry": entry, "rows": history_rows(entry)}
    return render(request, "docshelf/entry_history.html", context)


@login_on_denied
def version_file(request, slug, version_id, filename):
    return version_file_response(request, get_visible_entry(request, slug), version_id)

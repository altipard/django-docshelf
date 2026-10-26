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


class _LoginRequired(Exception):
    pass


def _get_entry(request, slug):
    entry = get_object_or_404(Entry.objects.with_versions(), slug=slug, is_published=True)
    if get_policy().can_view(request.user, entry):
        return entry
    if not request.user.is_authenticated:
        raise _LoginRequired
    raise PermissionDenied


def _login_on_denied(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except _LoginRequired:
            return redirect_to_login(request.get_full_path())

    return wrapper


def entry_list(request):
    """Visible entries grouped by category, in tree order."""
    today = timezone.localdate()
    show_expired = get_setting("SHOW_EXPIRED")
    entries = get_policy().filter_queryset(
        request.user, Entry.objects.select_related("category").with_versions()
    )
    by_category = defaultdict(list)
    for entry in entries:
        entry.current = entry.current_version(today)
        entry.current_status = entry.status(today)
        if entry.current is None and not (
            show_expired and entry.current_status == EntryStatus.EXPIRED
        ):
            continue
        by_category[entry.category_id].append(entry)
    sections = [(c, by_category[c.pk]) for c in Category.get_tree() if c.pk in by_category]
    return render(request, "docshelf/entry_list.html", {"sections": sections})


@_login_on_denied
def permalink(request, slug):
    """Stable URL of an entry, redirects to whatever version is current today."""
    entry = _get_entry(request, slug)
    version = entry.current_version()
    if version is None:
        raise Http404("No current version")
    target = version.get_file_url() if entry.kind_obj.needs_file else version.url
    response = HttpResponseRedirect(target)
    response["Cache-Control"] = "no-cache"
    return response


@_login_on_denied
def history(request, slug):
    entry = _get_entry(request, slug)
    statuses = version_statuses(entry.versions.all(), timezone.localdate())
    rows = [(v, s) for v, s in statuses.items() if s != VersionStatus.SCHEDULED]
    return render(request, "docshelf/entry_history.html", {"entry": entry, "rows": rows})


@_login_on_denied
def version_file(request, slug, version_id, filename):
    """One version's file. Only the id is used for the lookup, the file name is cosmetic."""
    entry = _get_entry(request, slug)
    version = next((v for v in entry.versions.all() if v.pk == version_id), None)
    if (
        version is None
        or not version.file
        or not entry.kind_obj.needs_file
        or version.valid_from > timezone.localdate()
    ):
        raise Http404("No such file")
    return serve(request, version, public=entry.audience == Audience.PUBLIC)

"""Who may see an entry.

The policy is used for lists, the permalink, the history and every file download. Replace it
with ``DOCSHELF_ACCESS_POLICY = "myproject.docshelf.Policy"``; a policy implements
``can_view(user, entry)`` and ``filter_queryset(user, queryset)``.
"""

from django.db.models import Q
from django.utils.module_loading import import_string

from .conf import get_setting
from .models import Audience


class DefaultPolicy:
    def can_view(self, user, entry):
        if not entry.is_published:
            return False
        if entry.audience == Audience.PUBLIC:
            return True
        if not user.is_authenticated:
            return False
        if entry.audience == Audience.AUTHENTICATED or user.is_superuser:
            return True
        return entry.groups.filter(pk__in=user.groups.values("pk")).exists()

    def filter_queryset(self, user, queryset):
        queryset = queryset.filter(is_published=True)
        if not user.is_authenticated:
            return queryset.filter(audience=Audience.PUBLIC)
        if user.is_superuser:
            return queryset
        return queryset.filter(
            Q(audience__in=[Audience.PUBLIC, Audience.AUTHENTICATED])
            | Q(audience=Audience.GROUPS, groups__in=user.groups.all())
        ).distinct()


def get_policy():
    return import_string(get_setting("ACCESS_POLICY"))()

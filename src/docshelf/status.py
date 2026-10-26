"""Version and entry status, derived from validity dates.

Status is never stored, so it cannot go stale. The functions work on plain iterables of
versions, which lets callers use prefetched querysets without extra queries.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class VersionStatus(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    CURRENT = "current", _("Current")
    SUPERSEDED = "superseded", _("Superseded")
    EXPIRED = "expired", _("Expired")


class EntryStatus(models.TextChoices):
    EMPTY = "empty", _("No versions")
    SCHEDULED = "scheduled", _("Scheduled")
    CURRENT = "current", _("Current")
    EXPIRED = "expired", _("Expired")


def _recency(version):
    # Same valid_from: the later created version wins.
    return (version.valid_from, version.pk or 0)


def _is_valid_on(version, day):
    if version.valid_from > day:
        return False
    return version.valid_until is None or version.valid_until >= day


def current_version(versions, day):
    valid = [v for v in versions if _is_valid_on(v, day)]
    return max(valid, key=_recency, default=None)


def version_statuses(versions, day):
    """Map each version to its status on ``day``."""
    versions = list(versions)
    current = current_version(versions, day)
    statuses = {}
    for version in versions:
        if version.valid_from > day:
            status = VersionStatus.SCHEDULED
        elif version is current:
            status = VersionStatus.CURRENT
        elif current is not None and _recency(version) < _recency(current):
            status = VersionStatus.SUPERSEDED
        else:
            status = VersionStatus.EXPIRED
        statuses[version] = status
    return statuses


def entry_status(versions, day):
    versions = list(versions)
    if not versions:
        return EntryStatus.EMPTY
    if current_version(versions, day) is not None:
        return EntryStatus.CURRENT
    if all(v.valid_from > day for v in versions):
        return EntryStatus.SCHEDULED
    return EntryStatus.EXPIRED

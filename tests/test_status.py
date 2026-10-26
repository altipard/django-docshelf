from dataclasses import dataclass
from datetime import date

from docshelf.status import (
    EntryStatus,
    VersionStatus,
    current_version,
    entry_status,
    version_statuses,
)

DAY = date(2026, 10, 26)


@dataclass(eq=False)
class v:
    pk: int
    valid_from: date
    valid_until: date | None = None


def test_newest_valid_version_is_current_older_ones_superseded():
    old, new = v(1, date(2021, 9, 18)), v(2, date(2024, 1, 15))
    assert current_version([old, new], DAY) is new
    assert version_statuses([old, new], DAY) == {
        old: VersionStatus.SUPERSEDED,
        new: VersionStatus.CURRENT,
    }


def test_future_version_is_scheduled_and_does_not_replace_current():
    current, future = v(1, date(2024, 1, 1)), v(2, date(2027, 1, 1))
    statuses = version_statuses([current, future], DAY)
    assert statuses[current] == VersionStatus.CURRENT
    assert statuses[future] == VersionStatus.SCHEDULED


def test_valid_from_today_and_valid_until_today_are_inclusive():
    assert current_version([v(1, DAY, DAY)], DAY) is not None


def test_expired_temporary_version_falls_back_to_older_one():
    base = v(1, date(2020, 1, 1))
    temporary = v(2, date(2026, 6, 1), date(2026, 8, 31))
    statuses = version_statuses([base, temporary], DAY)
    assert statuses[base] == VersionStatus.CURRENT
    assert statuses[temporary] == VersionStatus.EXPIRED


def test_same_valid_from_later_created_wins():
    first, second = v(1, date(2024, 1, 1)), v(2, date(2024, 1, 1))
    assert current_version([second, first], DAY) is second


def test_entry_status():
    assert entry_status([], DAY) == EntryStatus.EMPTY
    assert entry_status([v(1, date(2024, 1, 1))], DAY) == EntryStatus.CURRENT
    assert entry_status([v(1, date(2027, 1, 1))], DAY) == EntryStatus.SCHEDULED
    assert entry_status([v(1, date(2020, 1, 1), date(2021, 1, 1))], DAY) == EntryStatus.EXPIRED

"""Import existing documents into the catalogue.

Rows (one per version) come from a CSV file or from Wagtail documents. The import runs in two
phases: every row is resolved and validated first, without writing anything; only if no row
has an error are categories, entries and versions created. A second run with the same rows
creates nothing, because versions are matched by entry and content checksum.

CSV columns: entry_slug, title, category_path, kind, file, url, valid_from, valid_until, label,
change_note, audience, summary, issuer, old_url. ``file`` is a path relative to the base
directory or ``wagtaildoc:<id>``. ``category_path`` separates levels with ``/``.
"""

import csv
import hashlib
import os
from dataclasses import dataclass, field
from datetime import date

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify

from . import kinds
from .models import Audience, Category, Entry, Version

COLUMNS = [
    "entry_slug",
    "title",
    "category_path",
    "kind",
    "file",
    "url",
    "valid_from",
    "valid_until",
    "label",
    "change_note",
    "audience",
    "summary",
    "issuer",
    "old_url",
]

WAGTAILDOC_PREFIX = "wagtaildoc:"


class RowError(Exception):
    pass


@dataclass
class PlannedEntry:
    slug: str
    title: str
    category_path: list[str]
    kind: str
    audience: str
    summary: str
    issuer: str
    exists: bool


@dataclass
class PlannedVersion:
    line: int
    slug: str
    content: bytes | None
    filename: str
    url: str
    checksum: str
    valid_from: date
    valid_until: date | None
    label: str
    change_note: str
    old_url: str


@dataclass
class Report:
    entries_created: list[str] = field(default_factory=list)
    versions_created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    redirects: list[tuple[str, str]] = field(default_factory=list)


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in COLUMNS})


def _parse_date(value, name):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise RowError(f"{name}: expected YYYY-MM-DD, got {value!r}") from None


def _wagtail_document(value):
    try:
        from wagtail.documents import get_document_model
    except ImportError:
        raise RowError(f"{value!r} needs wagtail.documents installed") from None
    model = get_document_model()
    pk = value.removeprefix(WAGTAILDOC_PREFIX)
    try:
        return model.objects.get(pk=int(pk))
    except (ValueError, model.DoesNotExist):
        raise RowError(f"Wagtail document {pk!r} not found") from None


def _read_file(value, base_dir):
    """Return (content, filename, default old URL) for a ``file`` column value."""
    if value.startswith(WAGTAILDOC_PREFIX):
        document = _wagtail_document(value)
        with document.file.open("rb") as fh:
            content = fh.read()
        return content, os.path.basename(document.file.name), document.url
    path = os.path.join(base_dir, value)
    if not os.path.isfile(path):
        raise RowError(f"file not found: {path}")
    with open(path, "rb") as fh:
        return fh.read(), os.path.basename(path), ""


class Importer:
    def __init__(self, base_dir="."):
        self.base_dir = base_dir

    def run(self, rows, dry_run=False):
        report = Report()
        entries, versions = self.plan(rows, report)
        if report.errors or dry_run:
            return report
        with transaction.atomic():
            self.write(entries, versions, report)
        return report

    def plan(self, rows, report):
        entries = {}
        versions = []
        seen = set()
        for line, row in enumerate(rows, start=2):
            row = {key: (value or "").strip() for key, value in row.items() if key}
            try:
                entry = self._plan_entry(row, entries)
                version = self._plan_version(row, entry, line)
            except RowError as exc:
                report.errors.append(f"line {line}: {exc}")
                continue
            key = (entry.slug, version.checksum)
            imported = (
                entry.exists
                and Version.objects.filter(
                    entry__slug=entry.slug, checksum=version.checksum
                ).exists()
            )
            if imported or key in seen:
                report.skipped.append(f"line {line}: {entry.slug} version already imported")
                continue
            seen.add(key)
            versions.append(version)
        return entries, versions

    def _plan_entry(self, row, entries):
        slug = row.get("entry_slug") or slugify(row.get("title", ""))
        if not slug or slug != slugify(slug):
            raise RowError(f"invalid entry_slug {slug!r}")
        if slug in entries:
            return entries[slug]
        existing = Entry.objects.filter(slug=slug).first()
        if existing:
            entry = PlannedEntry(
                slug=slug,
                title=existing.title,
                category_path=[],
                kind=existing.kind,
                audience=existing.audience,
                summary=existing.summary,
                issuer=existing.issuer,
                exists=True,
            )
        else:
            kind = row.get("kind") or "file"
            try:
                kinds.get_kind(kind)
            except LookupError:
                raise RowError(f"unknown kind {kind!r}") from None
            audience = row.get("audience") or Audience.PUBLIC
            if audience not in Audience.values:
                raise RowError(f"unknown audience {audience!r}")
            path = [part.strip() for part in row.get("category_path", "").split("/")]
            path = [part for part in path if part]
            if not path:
                raise RowError("category_path is required for a new entry")
            if not row.get("title"):
                raise RowError("title is required for a new entry")
            entry = PlannedEntry(
                slug=slug,
                title=row["title"],
                category_path=path,
                kind=kind,
                audience=audience,
                summary=row.get("summary", ""),
                issuer=row.get("issuer", ""),
                exists=False,
            )
        entries[slug] = entry
        return entry

    def _plan_version(self, row, entry, line):
        needs_file = kinds.get_kind(entry.kind).needs_file
        file_value, url = row.get("file", ""), row.get("url", "")
        content, filename, default_old_url = None, "", ""
        if needs_file:
            if not file_value or url:
                raise RowError(f"kind {entry.kind!r} needs a file and no url")
            content, filename, default_old_url = _read_file(file_value, self.base_dir)
            checksum = hashlib.sha256(content).hexdigest()
        else:
            if not url or file_value:
                raise RowError(f"kind {entry.kind!r} needs a url and no file")
            checksum = hashlib.sha256(url.encode()).hexdigest()
        if not row.get("valid_from"):
            raise RowError("valid_from is required")
        valid_from = _parse_date(row["valid_from"], "valid_from")
        valid_until = (
            _parse_date(row["valid_until"], "valid_until") if row.get("valid_until") else None
        )
        if valid_until and valid_until < valid_from:
            raise RowError("valid_until is before valid_from")
        return PlannedVersion(
            line=line,
            slug=entry.slug,
            content=content,
            filename=filename,
            url=url,
            checksum=checksum,
            valid_from=valid_from,
            valid_until=valid_until,
            label=row.get("label", ""),
            change_note=row.get("change_note", ""),
            old_url=row.get("old_url") or default_old_url,
        )

    def write(self, entries, versions, report):
        slugs_with_versions = {v.slug for v in versions}
        saved = {}
        for slug, planned in entries.items():
            if slug not in slugs_with_versions:
                continue
            if planned.exists:
                saved[slug] = Entry.objects.get(slug=slug)
                continue
            saved[slug] = Entry.objects.create(
                slug=slug,
                title=planned.title,
                category=self._category(planned.category_path),
                kind=planned.kind,
                audience=planned.audience,
                summary=planned.summary,
                issuer=planned.issuer,
            )
            report.entries_created.append(slug)
        for planned in versions:
            entry = saved[planned.slug]
            version = Version(
                entry=entry,
                url=planned.url,
                valid_from=planned.valid_from,
                valid_until=planned.valid_until,
                label=planned.label,
                change_note=planned.change_note,
            )
            if planned.content is not None:
                version.file = ContentFile(planned.content, name=planned.filename)
            version.full_clean()
            version.save()
            report.versions_created.append(f"line {planned.line}: {entry.slug}")
            if planned.old_url:
                report.redirects.append((planned.old_url, entry.get_absolute_url()))

    def _category(self, path):
        parent = None
        for name in path:
            siblings = parent.get_children() if parent else Category.get_root_nodes()
            node = siblings.filter(name=name).first()
            if node is None:
                slug = _unique_category_slug(name)
                if parent:
                    node = parent.add_child(name=name, slug=slug)
                else:
                    node = Category.add_root(name=name, slug=slug)
            parent = node
        return parent


def _unique_category_slug(name):
    base = slugify(name) or "category"
    slug, n = base, 2
    while Category.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def rows_from_wagtaildocs(documents, category_path=""):
    """One row per Wagtail document, ready to import or to edit as CSV first."""
    return [
        {
            "entry_slug": slugify(document.title),
            "title": document.title,
            "category_path": category_path,
            "kind": "file",
            "file": f"{WAGTAILDOC_PREFIX}{document.pk}",
            "valid_from": document.created_at.date().isoformat(),
            "old_url": document.url,
        }
        for document in documents
    ]

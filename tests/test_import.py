import csv

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command

from docshelf.importing import COLUMNS
from docshelf.models import Category, Entry, Version

pytestmark = pytest.mark.django_db


@pytest.fixture
def import_dir(tmp_path):
    (tmp_path / "statutes-2019.pdf").write_bytes(b"2019")
    (tmp_path / "statutes-2021.pdf").write_bytes(b"2021")
    return tmp_path


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


STATUTES = [
    {
        "entry_slug": "statutes",
        "title": "Statutes",
        "category_path": "Club/Statutes & rules",
        "file": "statutes-2019.pdf",
        "valid_from": "2019-03-01",
        "label": "2019",
        "old_url": "/documents/15/satzung.pdf",
    },
    {
        "entry_slug": "statutes",
        "file": "statutes-2021.pdf",
        "valid_from": "2021-09-18",
        "label": "2021",
        "change_note": "Adopted by the general assembly",
    },
]

FORM = {
    "entry_slug": "membership",
    "title": "Membership application",
    "category_path": "Club/Membership",
    "kind": "form",
    "url": "https://forms.example.org/apply",
    "valid_from": "2024-01-01",
}


def test_csv_creates_categories_entries_and_versions(import_dir):
    path = write_rows(import_dir / "rows.csv", [*STATUTES, FORM])
    redirects = import_dir / "redirects.csv"
    call_command("docshelf_import", "csv", path, "--redirects", str(redirects))

    club = Category.objects.get(name="Club")
    assert [c.name for c in club.get_children()] == ["Statutes & rules", "Membership"]

    entry = Entry.objects.get(slug="statutes")
    assert entry.category.name == "Statutes & rules"
    versions = list(entry.versions.order_by("valid_from"))
    assert [v.label for v in versions] == ["2019", "2021"]
    assert versions[1].file.read() == b"2021"
    assert versions[1].change_note == "Adopted by the general assembly"
    assert Entry.objects.get(slug="membership").versions.get().url.endswith("/apply")

    with open(redirects, encoding="utf-8") as fh:
        assert list(csv.reader(fh)) == [
            ["old_url", "new_url"],
            ["/documents/15/satzung.pdf", "/documents/statutes/"],
        ]


def test_second_run_creates_nothing(import_dir, capsys):
    path = write_rows(import_dir / "rows.csv", [*STATUTES, FORM])
    call_command("docshelf_import", "csv", path)
    call_command("docshelf_import", "csv", path)
    assert Version.objects.count() == 3
    assert Category.objects.count() == 3
    assert "Created 0 entries and 0 versions, skipped 3." in capsys.readouterr().out


def test_new_version_for_existing_entry(import_dir):
    call_command("docshelf_import", "csv", write_rows(import_dir / "a.csv", STATUTES[:1]))
    call_command("docshelf_import", "csv", write_rows(import_dir / "b.csv", STATUTES[1:]))
    assert Entry.objects.get(slug="statutes").versions.count() == 2


def test_dry_run_writes_nothing(import_dir):
    path = write_rows(import_dir / "rows.csv", [*STATUTES, FORM])
    call_command("docshelf_import", "csv", path, "--dry-run")
    assert not Entry.objects.exists()
    assert not Category.objects.exists()


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"file": "missing.pdf"}, "file not found"),
        ({"valid_from": "18.09.2021"}, "expected YYYY-MM-DD"),
        ({"kind": "nope"}, "unknown kind"),
        ({"category_path": ""}, "category_path is required"),
        ({"url": "https://example.org"}, "needs a file and no url"),
        ({"valid_until": "2000-01-01"}, "before valid_from"),
    ],
)
def test_invalid_row_aborts_whole_import(import_dir, capsys, bad, message):
    rows = [{**STATUTES[0], **bad}, FORM]
    with pytest.raises(CommandError, match="nothing was imported"):
        call_command("docshelf_import", "csv", write_rows(import_dir / "rows.csv", rows))
    assert message in capsys.readouterr().err
    assert not Entry.objects.exists()
    assert not Category.objects.exists()


class TestWagtailDocuments:
    @pytest.fixture
    def documents(self):
        if not settings.HAS_WAGTAIL:
            pytest.skip("wagtail not installed")
        from django.core.files.base import ContentFile
        from wagtail.documents import get_document_model

        model = get_document_model()
        return [
            model.objects.create(title="Satzung", file=ContentFile(b"2019", name="satzung.pdf")),
            model.objects.create(
                title="Satzung 2021", file=ContentFile(b"2021", name="20210918_Satzung.pdf")
            ),
        ]

    def test_direct_import_copies_files(self, documents, tmp_path):
        redirects = tmp_path / "redirects.csv"
        call_command(
            "docshelf_import",
            "wagtaildocs",
            "--ids",
            str(documents[0].pk),
            "--category",
            "Club",
            "--redirects",
            str(redirects),
        )
        version = Entry.objects.get(slug="satzung").versions.get()
        assert version.file.read() == b"2019"
        assert version.file.name != documents[0].file.name
        assert documents[0].file.storage.exists(documents[0].file.name)
        assert documents[0].url in redirects.read_text()

    def test_emit_csv_then_merge_versions(self, documents, tmp_path):
        emitted = tmp_path / "docs.csv"
        ids = [str(d.pk) for d in documents]
        call_command("docshelf_import", "wagtaildocs", "--ids", *ids, "--emit-csv", str(emitted))
        assert not Entry.objects.exists()

        with open(emitted, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for row in rows:
            row.update(entry_slug="statutes", title="Statutes", category_path="Club")
        rows[1]["valid_from"] = "2021-09-18"
        call_command("docshelf_import", "csv", write_rows(tmp_path / "edited.csv", rows))

        entry = Entry.objects.get(slug="statutes")
        assert sorted(v.file.read() for v in entry.versions.all()) == [b"2019", b"2021"]

    def test_requires_selection_and_category(self, documents):
        with pytest.raises(CommandError, match="--ids, --collection or --tag"):
            call_command("docshelf_import", "wagtaildocs", "--category", "Club")
        with pytest.raises(CommandError, match="--category is required"):
            call_command("docshelf_import", "wagtaildocs", "--ids", str(documents[0].pk))

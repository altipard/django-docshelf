import csv
import os

from django.core.management.base import BaseCommand, CommandError

from docshelf.importing import Importer, read_csv, rows_from_wagtaildocs, write_csv


class Command(BaseCommand):
    help = (
        "Import documents into docshelf from a CSV file or from Wagtail documents. Nothing is "
        "written unless every row is valid; a second run skips versions already imported."
    )

    def add_arguments(self, parser):
        sources = parser.add_subparsers(dest="source", required=True)

        from_csv = sources.add_parser("csv", help="One row per version, see docshelf.importing.")
        from_csv.add_argument("path")
        from_csv.add_argument(
            "--base-dir", help="Directory for relative file paths (default: the CSV's directory)."
        )

        docs = sources.add_parser("wagtaildocs", help="One entry per Wagtail document.")
        docs.add_argument("--ids", nargs="+", type=int, help="Document IDs.")
        docs.add_argument("--collection", help="Collection name.")
        docs.add_argument("--tag", help="Tag name.")
        docs.add_argument("--category", default="", help="Category path, e.g. 'Club/Statutes'.")
        docs.add_argument(
            "--emit-csv",
            metavar="PATH",
            help="Write the rows as CSV to edit them (merge versions, set categories) "
            "and import with the csv source, instead of importing directly.",
        )

        for sub in (from_csv, docs):
            sub.add_argument("--dry-run", action="store_true", help="Validate only.")
            sub.add_argument(
                "--redirects",
                metavar="PATH",
                help="Write old URL → permalink pairs as CSV for the project's redirects.",
            )

    def handle(self, *args, source, dry_run, redirects, **options):
        if source == "csv":
            rows = read_csv(options["path"])
            base_dir = options["base_dir"] or os.path.dirname(os.path.abspath(options["path"]))
        else:
            rows = rows_from_wagtaildocs(self._documents(options), options["category"])
            if options["emit_csv"]:
                write_csv(options["emit_csv"], rows)
                self.stdout.write(f"Wrote {len(rows)} rows to {options['emit_csv']}.")
                return
            base_dir = "."

        report = Importer(base_dir=base_dir).run(rows, dry_run=dry_run)

        for line in report.skipped:
            self.stdout.write(f"skipped {line}")
        for line in report.errors:
            self.stderr.write(self.style.ERROR(line))
        if report.errors:
            raise CommandError(f"{len(report.errors)} invalid rows, nothing was imported.")
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"{len(rows)} rows are valid (dry run)."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(report.entries_created)} entries and "
                f"{len(report.versions_created)} versions, "
                f"skipped {len(report.skipped)}."
            )
        )
        if redirects:
            with open(redirects, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["old_url", "new_url"])
                writer.writerows(report.redirects)
            self.stdout.write(f"Wrote {len(report.redirects)} redirects to {redirects}.")

    def _documents(self, options):
        try:
            from wagtail.documents import get_document_model
        except ImportError:
            raise CommandError("The wagtaildocs source needs wagtail.documents.") from None
        if not (options["ids"] or options["collection"] or options["tag"]):
            raise CommandError("Select documents with --ids, --collection or --tag.")
        if not options["emit_csv"] and not options["category"]:
            raise CommandError("--category is required unless --emit-csv is used.")
        documents = get_document_model().objects.order_by("pk")
        if options["ids"]:
            documents = documents.filter(pk__in=options["ids"])
        if options["collection"]:
            documents = documents.filter(collection__name=options["collection"])
        if options["tag"]:
            documents = documents.filter(tags__name=options["tag"])
        return documents.distinct()

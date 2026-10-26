from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from wagtail.models import Page

from docshelf.contrib.wagtail.models import LibraryPage
from docshelf.models import Audience, Category, Entry, Version


def pdf(text):
    """A one-page PDF showing ``text``, built by hand to keep the demo dependency-free."""
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


class Command(BaseCommand):
    help = "Create demo categories, entries and a library page. Wipes existing docshelf data."

    def handle(self, *args, **options):
        Version.objects.all().delete()
        Entry.objects.all().delete()
        Category.objects.all().delete()
        LibraryPage.objects.all().delete()

        user_model = get_user_model()
        if not user_model.objects.filter(username="admin").exists():
            user_model.objects.create_superuser("admin", "admin@example.org", "admin")
        members, _ = Group.objects.get_or_create(name="Members")

        club = Category.add_root(name="Club", slug="club")
        membership = club.add_child(name="Membership & applications", slug="membership")
        rules = club.add_child(name="Statutes & rules", slug="statutes-rules")
        meetings = club.add_child(name="Meetings", slug="meetings")
        law = Category.add_root(name="Law & authorities", slug="law")
        acts = law.add_child(name="Laws & regulations", slug="laws")

        today = date.today()

        def entry(category, slug, title, kind="file", **fields):
            return Entry.objects.create(
                category=category, slug=slug, title=title, kind=kind, **fields
            )

        def version(entry, valid_from, text=None, url="", **fields):
            obj = Version(entry=entry, valid_from=valid_from, url=url, **fields)
            if text:
                obj.file = ContentFile(pdf(text), name=f"{entry.slug}.pdf")
            obj.full_clean()
            obj.save()

        statutes = entry(rules, "statutes", "Statutes", summary="Constitution of the club.")
        version(statutes, date(2019, 3, 1), "Statutes 2019", label="Version of 2019")
        version(
            statutes,
            date(2021, 9, 18),
            "Statutes 2021",
            label="Adopted by the general assembly on 2021-09-18",
            change_note="Board extended to five members.",
        )

        fishing = entry(
            rules,
            "fishing-rules",
            "Fishing and water rules",
            issuer="Board",
            review_due=today - timedelta(days=10),
        )
        version(fishing, date(2024, 1, 15), "Fishing rules 2024")
        version(
            fishing,
            today + timedelta(days=60),
            "Fishing rules next season",
            label="Next season",
        )

        apply = entry(membership, "membership-application", "Membership application", "form")
        version(apply, date(2024, 1, 1), url="https://example.org/forms/membership")

        minutes = entry(
            meetings,
            "minutes-2025",
            "Minutes of the general assembly 2025",
            audience=Audience.GROUPS,
            summary="Visible to members only.",
        )
        minutes.groups.add(members)
        version(minutes, date(2025, 3, 20), "Minutes 2025")

        act = entry(acts, "fisheries-act", "State fisheries act", "link", issuer="State")
        version(act, date(2020, 1, 1), url="https://example.org/law/fisheries-act")

        home = Page.objects.get(depth=2)
        home.add_child(instance=LibraryPage(title="Documents", slug="documents"))

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data created. Run the server and open http://localhost:8000/documents/ "
                "(admin: admin / admin at http://localhost:8000/admin/)."
            )
        )

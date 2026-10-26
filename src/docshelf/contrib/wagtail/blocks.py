from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.snippets.blocks import SnippetChooserBlock

from docshelf.access import get_policy
from docshelf.conf import get_setting
from docshelf.status import EntryStatus
from docshelf.views import build_sections


def _user(parent_context):
    request = (parent_context or {}).get("request")
    return getattr(request, "user", None) or AnonymousUser()


class EntryBlock(SnippetChooserBlock):
    """A single entry as a card. Renders nothing if the visitor may not see it."""

    def __init__(self, **kwargs):
        super().__init__("docshelf.Entry", **kwargs)

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        entry = value
        if entry is not None and get_policy().can_view(_user(parent_context), entry):
            day = timezone.localdate()
            entry.current = entry.current_version(day)
            entry.current_status = entry.status(day)
            if entry.current is None and not (
                get_setting("SHOW_EXPIRED") and entry.current_status == EntryStatus.EXPIRED
            ):
                entry = None
        else:
            entry = None
        context["entry"] = entry
        return context

    class Meta:
        icon = "doc-full"
        label = _("Document")
        template = "docshelf_wagtail/blocks/entry.html"


class CategoryBlock(blocks.StructBlock):
    """All visible entries of a category, optionally including subcategories."""

    category = SnippetChooserBlock("docshelf.Category", label=_("Category"))
    include_subcategories = blocks.BooleanBlock(
        required=False, default=True, label=_("Include subcategories")
    )

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        category = value.get("category")
        context["sections"] = (
            build_sections(
                _user(parent_context),
                root=category,
                include_descendants=value.get("include_subcategories"),
            )
            if category is not None
            else []
        )
        context["hide_filter"] = True
        return context

    class Meta:
        icon = "folder-open-inverse"
        label = _("Document category")
        template = "docshelf_wagtail/blocks/category.html"

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel, ObjectList
from wagtail.admin.ui.components import Component
from wagtail.admin.ui.tables import Column
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from docshelf.models import Category, Entry

from .forms import CategoryForm, EntryForm


class CategoryViewSet(SnippetViewSet):
    model = Category
    icon = "folder-open-inverse"
    menu_label = _("Categories")
    ordering = ["path"]
    search_fields = ["name", "slug", "description"]
    search_backend_name = None
    list_display = [
        "name",
        "slug",
        Column("parent", label=_("Parent category"), accessor=lambda c: c.get_parent() or ""),
    ]
    edit_handler = ObjectList(
        [FieldPanel("name"), FieldPanel("slug"), FieldPanel("parent"), FieldPanel("description")],
        base_form_class=CategoryForm,
    )


class EntryViewSet(SnippetViewSet):
    model = Entry
    icon = "doc-full-inverse"
    menu_label = _("Entries")
    search_fields = ["title", "slug", "summary", "issuer"]
    search_backend_name = None
    list_display = [
        "title",
        "category",
        Column("kind", label=_("Kind"), accessor="get_kind_display"),
        Column("status", label=_("Status"), accessor=lambda e: e.status().label),
        "review_due",
        "is_published",
    ]
    list_filter = ["category", "kind", "audience", "is_published"]
    edit_handler = ObjectList(
        [
            FieldPanel("title"),
            FieldPanel("slug"),
            FieldPanel("summary"),
            FieldPanel("category"),
            FieldPanel("kind"),
            FieldPanel("sort_order"),
            MultiFieldPanel(
                [FieldPanel("is_published"), FieldPanel("audience"), FieldPanel("groups")],
                heading=_("Access"),
            ),
            MultiFieldPanel(
                [FieldPanel("issuer"), FieldPanel("review_due")],
                heading=_("Maintenance"),
            ),
            InlinePanel(
                "versions",
                label=_("Versions"),
                panels=[
                    FieldPanel("label"),
                    FieldPanel("file"),
                    FieldPanel("url"),
                    FieldPanel("valid_from"),
                    FieldPanel("valid_until"),
                    FieldPanel("change_note"),
                ],
            ),
        ],
        base_form_class=EntryForm,
    )

    def get_queryset(self, request):
        return Entry.objects.select_related("category").with_versions()


class DocumentLibraryGroup(SnippetViewSetGroup):
    items = (EntryViewSet, CategoryViewSet)
    menu_label = _("Documents")
    menu_icon = "folder-open-inverse"
    menu_name = "docshelf"


register_snippet(DocumentLibraryGroup)


class ReviewOverduePanel(Component):
    name = "docshelf_review_overdue"
    template_name = "docshelf_wagtail/home/review_overdue.html"
    order = 260

    def get_context_data(self, parent_context):
        context = super().get_context_data(parent_context)
        context["entries"] = Entry.objects.filter(review_due__lt=timezone.localdate()).order_by(
            "review_due"
        )[:10]
        return context


@hooks.register("construct_homepage_panels")
def add_review_overdue_panel(request, panels):
    if request.user.has_perm("docshelf.change_entry"):
        panels.append(ReviewOverduePanel())

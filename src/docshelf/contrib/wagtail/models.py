from django.db import models
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import RichTextField
from wagtail.models import Page

from docshelf import views
from docshelf.models import Category


class LibraryPage(RoutablePageMixin, Page):
    """Serves the document library below a page: list, permalinks, history and files."""

    intro = RichTextField(_("introduction"), blank=True)
    root_category = models.ForeignKey(
        Category,
        verbose_name=_("root category"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=_("Only list entries in this category and below. Empty lists all."),
    )

    content_panels = Page.content_panels + [FieldPanel("intro"), FieldPanel("root_category")]

    template = "docshelf_wagtail/library_page.html"
    history_template = "docshelf/entry_history.html"

    class Meta:
        verbose_name = _("document library")

    @path("", name="list")
    def library_index(self, request):
        sections = views.build_sections(request.user, root=self.root_category)
        return self.render(request, context_overrides={"sections": sections})

    @path("<slug:slug>/", name="permalink")
    @views.login_on_denied
    def library_permalink(self, request, slug):
        return views.permalink_response(views.get_visible_entry(request, slug))

    @path("<slug:slug>/history/", name="history")
    @views.login_on_denied
    def library_history(self, request, slug):
        entry = views.get_visible_entry(request, slug)
        context = self.get_context(request)
        context.update(entry=entry, rows=views.history_rows(entry))
        return TemplateResponse(request, self.history_template, context)

    # Wagtail only routes paths ending in a slash without dots, so the file name is not part of
    # the URL here; Content-Disposition still carries it.
    @path("<slug:slug>/v/<int:version_id>/", name="version_file")
    @views.login_on_denied
    def library_version_file(self, request, slug, version_id):
        entry = views.get_visible_entry(request, slug)
        return views.version_file_response(request, entry, version_id)

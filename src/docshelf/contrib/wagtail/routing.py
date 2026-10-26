"""URLs of entries below a ``LibraryPage``.

Enable with ``DOCSHELF_ROUTER = "docshelf.contrib.wagtail.routing.LibraryPageRouter"``. With
several library pages, an entry belongs to the live page with the most specific root category
that contains it; a page without root category takes everything else.
"""

from django.urls import NoReverseMatch

_pages = None


def clear_cache(**kwargs):
    global _pages
    _pages = None


def _library_pages():
    global _pages
    if _pages is None:
        from .models import LibraryPage

        _pages = list(LibraryPage.objects.live().select_related("root_category"))
    return _pages


class LibraryPageRouter:
    def page_for(self, entry):
        best, best_depth = None, -1
        for page in _library_pages():
            root = page.root_category
            if root is not None and not entry.category.path.startswith(root.path):
                continue
            depth = root.depth if root is not None else 0
            if depth > best_depth:
                best, best_depth = page, depth
        if best is None:
            raise NoReverseMatch(f"No live LibraryPage serves {entry.slug!r}")
        return best

    def _url(self, entry, name, args):
        page = self.page_for(entry)
        return page.get_url() + page.reverse_subpage(name, args=args)

    def permalink(self, entry):
        return self._url(entry, "permalink", [entry.slug])

    def history(self, entry):
        return self._url(entry, "history", [entry.slug])

    def version_file(self, version):
        entry = version.entry
        return self._url(entry, "version_file", [entry.slug, version.pk])

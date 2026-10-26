"""Where the public URLs of entries and versions live.

The default router reverses the URLs from ``include("docshelf.urls")``. Wagtail projects that
serve the library through a ``LibraryPage`` set
``DOCSHELF_ROUTER = "docshelf.contrib.wagtail.routing.LibraryPageRouter"``.
"""

from django.urls import reverse
from django.utils.module_loading import import_string

from .conf import get_setting


class NamespaceRouter:
    namespace = "docshelf"

    def permalink(self, entry):
        return reverse(f"{self.namespace}:permalink", args=[entry.slug])

    def history(self, entry):
        return reverse(f"{self.namespace}:history", args=[entry.slug])

    def version_file(self, version):
        return reverse(
            f"{self.namespace}:version_file",
            args=[version.entry.slug, version.pk, version.filename],
        )


def get_router():
    return import_string(get_setting("ROUTER"))()

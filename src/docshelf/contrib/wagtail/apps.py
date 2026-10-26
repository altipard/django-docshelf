from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocshelfWagtailConfig(AppConfig):
    name = "docshelf.contrib.wagtail"
    label = "docshelf_wagtail"
    verbose_name = _("Document library (Wagtail)")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.db.models.signals import post_delete, post_save
        from wagtail.signals import page_published, page_unpublished

        from .models import LibraryPage
        from .routing import clear_cache

        for signal in (page_published, page_unpublished, post_save, post_delete):
            signal.connect(clear_cache, sender=LibraryPage, dispatch_uid=f"docshelf_{signal!r}")

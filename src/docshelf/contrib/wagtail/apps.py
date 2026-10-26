from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocshelfWagtailConfig(AppConfig):
    name = "docshelf.contrib.wagtail"
    label = "docshelf_wagtail"
    verbose_name = _("Document library (Wagtail)")
    default_auto_field = "django.db.models.BigAutoField"

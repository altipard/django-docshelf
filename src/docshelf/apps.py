from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DocshelfConfig(AppConfig):
    name = "docshelf"
    verbose_name = _("Document library")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import checks, signals  # noqa: F401

from django.conf import settings
from django.core.checks import Warning, register

from .conf import get_setting


@register()
def check_storage(app_configs, **kwargs):
    alias = get_setting("STORAGE")
    if alias in getattr(settings, "STORAGES", {}):
        return []
    return [
        Warning(
            f"STORAGES has no {alias!r} entry, docshelf files go to the default storage.",
            hint=(
                "Files in the default storage are usually served directly by the web server, "
                "which bypasses docshelf access rules. Add a storage outside MEDIA_ROOT, e.g. "
                f'STORAGES[{alias!r}] = {{"BACKEND": '
                '"django.core.files.storage.FileSystemStorage", '
                '"OPTIONS": {"location": BASE_DIR / "private-media"}}.'
            ),
            id="docshelf.W001",
        )
    ]

from django.conf import settings

DEFAULTS = {
    "STORAGE": "docshelf",
    "SHOW_EXPIRED": False,
}


def get_setting(name):
    return getattr(settings, f"DOCSHELF_{name}", DEFAULTS[name])

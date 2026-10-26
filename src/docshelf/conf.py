from django.conf import settings

DEFAULTS = {
    "STORAGE": "docshelf",
    "SHOW_EXPIRED": False,
    "SERVE_BACKEND": "django",
    "X_ACCEL_PREFIX": "/protected/docshelf/",
    "ACCESS_POLICY": "docshelf.access.DefaultPolicy",
}


def get_setting(name):
    return getattr(settings, f"DOCSHELF_{name}", DEFAULTS[name])

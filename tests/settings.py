from importlib.util import find_spec

SECRET_KEY = "docshelf-tests"
USE_TZ = True

HAS_WAGTAIL = find_spec("wagtail") is not None

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "treebeard",
    "docshelf",
]

if HAS_WAGTAIL:
    INSTALLED_APPS += [
        "taggit",
        "modelcluster",
        "wagtail",
        "docshelf.contrib.wagtail",
    ]

STATIC_URL = "/static/"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

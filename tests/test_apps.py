import pytest
from django.apps import apps
from django.conf import settings


def test_core_app_is_installed():
    assert apps.is_installed("docshelf")


@pytest.mark.skipif(not settings.HAS_WAGTAIL, reason="wagtail not installed")
def test_wagtail_app_is_installed():
    assert apps.get_app_config("docshelf_wagtail").name == "docshelf.contrib.wagtail"

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("documents/", include("docshelf.urls")),
]

if settings.HAS_WAGTAIL:
    from wagtail import urls as wagtail_urls
    from wagtail.admin import urls as wagtailadmin_urls
    from wagtail.documents import urls as wagtaildocs_urls

    urlpatterns += [
        path("cms/", include(wagtailadmin_urls)),
        path("wagtail-documents/", include(wagtaildocs_urls)),
        path("", include(wagtail_urls)),
    ]

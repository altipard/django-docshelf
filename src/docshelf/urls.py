from django.urls import path

from . import views

app_name = "docshelf"

urlpatterns = [
    path("", views.entry_list, name="list"),
    path("<slug:slug>/", views.permalink, name="permalink"),
    path("<slug:slug>/history/", views.history, name="history"),
    path(
        "<slug:slug>/v/<int:version_id>/<str:filename>",
        views.version_file,
        name="version_file",
    ),
]

from django import forms
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from . import status
from .models import Category, Entry, Version


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    form = movenodeform_factory(Category)
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name", "slug", "description"]


def _formfield(db_field, **kwargs):
    if db_field.name == "url":
        # Same behaviour on Django 5.2 as on 6.x, where https is the default.
        kwargs["assume_scheme"] = "https"
    return db_field.formfield(**kwargs)


class VersionForm(forms.ModelForm):
    class Meta:
        model = Version
        fields = ["label", "file", "url", "valid_from", "valid_until", "change_note"]
        formfield_callback = _formfield

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            for name in ("file", "url"):
                self.fields[name].disabled = True
                self.fields[name].help_text = _("Fixed once saved. Add a new version instead.")


class VersionInline(admin.StackedInline):
    model = Version
    form = VersionForm
    extra = 0
    readonly_fields = ["status_label", "checksum", "size", "created_at", "created_by"]
    fields = [
        "status_label",
        "label",
        ("file", "url"),
        ("valid_from", "valid_until"),
        "change_note",
        ("checksum", "size"),
        ("created_at", "created_by"),
    ]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "url":
            kwargs["assume_scheme"] = "https"
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description=_("status"))
    def status_label(self, obj):
        if not obj.pk:
            return "-"
        statuses = status.version_statuses(obj.entry.versions.all(), timezone.localdate())
        return statuses[obj].label


class ReviewDueFilter(admin.SimpleListFilter):
    title = _("review")
    parameter_name = "review"

    def lookups(self, request, model_admin):
        return [("overdue", _("Overdue"))]

    def queryset(self, request, queryset):
        if self.value() == "overdue":
            return queryset.filter(review_due__lt=timezone.localdate())
        return queryset


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "kind",
        "audience",
        "status_label",
        "review_due",
        "is_published",
    ]
    list_filter = [
        "kind",
        "audience",
        "is_published",
        ReviewDueFilter,
        ("category", admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = ["title", "slug", "summary", "issuer"]
    prepopulated_fields = {"slug": ["title"]}
    filter_horizontal = ["groups"]
    inlines = [VersionInline]
    fieldsets = [
        (None, {"fields": ["title", "slug", "summary", "category", "kind", "sort_order"]}),
        (_("Access"), {"fields": ["is_published", "audience", "groups"]}),
        (_("Maintenance"), {"fields": ["issuer", "review_due"]}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category").with_versions()

    @admin.display(description=_("status"))
    def status_label(self, obj):
        return obj.status().label

    def save_formset(self, request, form, formset, change):
        for version_form in formset.forms:
            version = version_form.instance
            if not version.pk and version.created_by_id is None:
                version.created_by = request.user
        super().save_formset(request, form, formset, change)

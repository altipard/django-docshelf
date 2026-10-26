from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms import WagtailAdminModelForm

from docshelf.models import Category


class CategoryParentField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "— " * (obj.depth - 1) + obj.name


class CategoryForm(WagtailAdminModelForm):
    """Places the category in the tree; treebeard nodes cannot be created with ``save()``."""

    parent = CategoryParentField(
        queryset=Category.objects.order_by("path"),
        required=False,
        label=_("Parent category"),
        help_text=_("Leave empty for a top-level category."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["parent"].initial = self.instance.get_parent()
            # A category cannot move below itself.
            self.fields["parent"].queryset = Category.objects.exclude(
                path__startswith=self.instance.path
            ).order_by("path")

    def save(self, commit=True):
        instance = super().save(commit=False)
        parent = self.cleaned_data.get("parent")
        if instance.pk is None:
            if parent:
                return parent.add_child(instance=instance)
            return Category.add_root(instance=instance)
        instance.save()
        if parent != instance.get_parent():
            if parent:
                instance.move(parent, "last-child")
            else:
                instance.move(Category.get_last_root_node(), "last-sibling")
            instance.refresh_from_db()
        return instance


class EntryForm(WagtailAdminModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self._version_forms():
            if form.instance.pk:
                for name in ("file", "url"):
                    if name in form.fields:
                        form.fields[name].disabled = True
                        form.fields[name].help_text = _(
                            "Fixed once saved. Add a new version instead."
                        )

    def save(self, commit=True):
        user = self.for_user
        if user is not None and user.is_authenticated:
            for form in self._version_forms():
                if not form.instance.pk and form.instance.created_by_id is None:
                    form.instance.created_by = user
        return super().save(commit=commit)

    def _version_forms(self):
        formset = self.formsets.get("versions")
        return formset.forms if formset is not None else []

import hashlib
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from . import kinds, status
from .storage import get_storage, version_upload_to


class Category(MP_Node):
    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, unique=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def __str__(self):
        return self.name


class Audience(models.TextChoices):
    PUBLIC = "public", _("Public")
    AUTHENTICATED = "authenticated", _("Signed-in users")
    GROUPS = "groups", _("Selected groups")


class EntryQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def with_versions(self):
        return self.prefetch_related("versions")


class Entry(models.Model):
    title = models.CharField(_("title"), max_length=255)
    slug = models.SlugField(
        _("slug"),
        max_length=255,
        unique=True,
        help_text=_("Part of the permanent link. Changing it breaks existing links."),
    )
    summary = models.TextField(_("summary"), blank=True)
    category = models.ForeignKey(
        Category,
        verbose_name=_("category"),
        on_delete=models.PROTECT,
        related_name="entries",
    )
    kind = models.CharField(_("kind"), max_length=32, choices=kinds.get_choices)
    audience = models.CharField(
        _("audience"), max_length=32, choices=Audience.choices, default=Audience.PUBLIC
    )
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name=_("groups"),
        blank=True,
        related_name="+",
        help_text=_("Only used when the audience is 'Selected groups'."),
    )
    issuer = models.CharField(
        _("issuer"),
        max_length=255,
        blank=True,
        help_text=_("Who issues the document, e.g. 'Board' or 'Federal state'."),
    )
    review_due = models.DateField(
        _("review due"),
        null=True,
        blank=True,
        help_text=_("Date by which the entry should be checked for being up to date."),
    )
    is_published = models.BooleanField(_("published"), default=True)
    sort_order = models.PositiveIntegerField(_("sort order"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = EntryQuerySet.as_manager()

    class Meta:
        ordering = ["sort_order", "title"]
        verbose_name = _("entry")
        verbose_name_plural = _("entries")

    def __str__(self):
        return self.title

    @property
    def kind_obj(self):
        return kinds.get_kind(self.kind)

    def clean(self):
        super().clean()
        if not self.pk or not self.kind:
            return
        previous = Entry.objects.filter(pk=self.pk).values_list("kind", flat=True).first()
        if previous and previous != self.kind and self.versions.exists():
            try:
                changes_target = kinds.get_kind(previous).target != self.kind_obj.target
            except LookupError:
                changes_target = True
            if changes_target:
                raise ValidationError(
                    {"kind": _("Existing versions do not match this kind. Create a new entry.")}
                )

    def current_version(self, day=None):
        return status.current_version(self.versions.all(), day or timezone.localdate())

    def status(self, day=None):
        return status.entry_status(self.versions.all(), day or timezone.localdate())

    @property
    def is_review_overdue(self):
        return self.review_due is not None and self.review_due < timezone.localdate()


class Version(models.Model):
    entry = models.ForeignKey(
        Entry, verbose_name=_("entry"), on_delete=models.CASCADE, related_name="versions"
    )
    label = models.CharField(
        _("label"),
        max_length=255,
        blank=True,
        help_text=_("For example 'Adopted by the general assembly on 2021-09-18'."),
    )
    file = models.FileField(
        _("file"),
        storage=get_storage,
        upload_to=version_upload_to,
        max_length=500,
        blank=True,
    )
    url = models.URLField(_("URL"), max_length=2000, blank=True)
    valid_from = models.DateField(_("valid from"), default=timezone.localdate)
    valid_until = models.DateField(_("valid until"), null=True, blank=True)
    change_note = models.TextField(_("change note"), blank=True)
    checksum = models.CharField(_("SHA-256"), max_length=64, blank=True, editable=False)
    size = models.PositiveBigIntegerField(_("size"), null=True, blank=True, editable=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-valid_from", "-pk"]
        verbose_name = _("version")
        verbose_name_plural = _("versions")
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=F("valid_from")),
                name="docshelf_version_valid_range",
            ),
            models.CheckConstraint(
                condition=Q(file="") | Q(url=""),
                name="docshelf_version_single_target",
            ),
        ]

    def __str__(self):
        return self.label or f"{self.entry} ({self.valid_from:%Y-%m-%d})"

    def save(self, *args, **kwargs):
        if self.target_changed:
            raise ValueError("The file or URL of an existing version cannot be changed.")
        if not self.checksum:
            self.checksum, self.size = self._fingerprint()
        super().save(*args, **kwargs)
        self._loaded_target = self._target()

    @classmethod
    def from_db(cls, *args, **kwargs):
        # Django 6.1 added the keyword-only argument ``fetch_mode``, pass everything through.
        instance = super().from_db(*args, **kwargs)
        instance._loaded_target = instance._target()
        return instance

    def _target(self):
        file_name = self.__dict__.get("file")
        return (getattr(file_name, "name", file_name) or "", self.__dict__.get("url") or "")

    @property
    def target_changed(self):
        loaded = getattr(self, "_loaded_target", None)
        return loaded is not None and loaded != self._target()

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""

    def clean(self):
        super().clean()
        errors = {}
        if self.target_changed:
            errors["__all__"] = _(
                "The file or URL of an existing version cannot be changed. Add a new version."
            )
        if self.file and self.url:
            errors["url"] = _("Set either a file or a URL, not both.")
        elif self.entry_id or getattr(self, "entry", None):
            try:
                kind = self.entry.kind_obj
            except LookupError:
                kind = None
            if kind and kind.needs_file and not self.file:
                errors["file"] = _("This kind needs a file.")
            if kind and not kind.needs_file and not self.url:
                errors["url"] = _("This kind needs a URL.")
            if kind and not kind.needs_file and self.file:
                errors["file"] = _("This kind links to a URL and takes no file.")
        if self.valid_until and self.valid_from and self.valid_until < self.valid_from:
            errors["valid_until"] = _("Must not be before 'valid from'.")
        if errors:
            raise ValidationError(errors)

    def _fingerprint(self):
        digest = hashlib.sha256()
        if self.file:
            size = 0
            self.file.open("rb")
            for chunk in self.file.chunks():
                digest.update(chunk)
                size += len(chunk)
            self.file.seek(0)
            return digest.hexdigest(), size
        if self.url:
            digest.update(self.url.encode())
            return digest.hexdigest(), None
        return "", None

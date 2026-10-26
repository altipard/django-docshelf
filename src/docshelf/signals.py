from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Version


@receiver(post_delete, sender=Version, dispatch_uid="docshelf_delete_version_file")
def delete_version_file(sender, instance, **kwargs):
    # Files are immutable and belong to exactly one version, so they go with it. Deleting after
    # commit keeps the file when the surrounding transaction rolls back.
    if instance.file:
        storage, name = instance.file.storage, instance.file.name
        transaction.on_commit(lambda: storage.delete(name))

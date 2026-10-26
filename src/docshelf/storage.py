from uuid import uuid4

from django.core.files.storage import default_storage, storages
from django.core.files.storage.handler import InvalidStorageError

from .conf import get_setting


def get_storage():
    """Storage for version files, ``STORAGES[DOCSHELF_STORAGE]`` or the default storage.

    The fallback keeps a fresh install working; system check ``docshelf.W001`` warns about it
    because files in the default storage are usually served without access checks.
    """
    try:
        return storages[get_setting("STORAGE")]
    except InvalidStorageError:
        return default_storage


def version_upload_to(instance, filename):
    # The random segment keeps every upload in its own path, so no version can overwrite
    # another one, even with identical file names.
    return f"{instance.entry.slug}/{uuid4().hex}/{filename}"

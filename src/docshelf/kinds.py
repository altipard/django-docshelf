"""Registry of entry kinds.

A kind decides whether the versions of an entry point to an uploaded file or to a URL, and how
the entry is labelled. Projects add kinds in ``AppConfig.ready()``::

    from docshelf.kinds import Kind, register

    register(Kind("map", _("Map"), target=Kind.URL, icon="map"))
"""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Kind:
    FILE = "file"
    URL = "url"

    name: str
    label: str
    target: str
    icon: str = ""

    def __post_init__(self):
        if self.target not in (self.FILE, self.URL):
            raise ValueError(f"Kind {self.name!r}: target must be 'file' or 'url'")

    @property
    def needs_file(self):
        return self.target == self.FILE


_registry: dict[str, Kind] = {}


def register(kind):
    _registry[kind.name] = kind
    return kind


def unregister(name):
    _registry.pop(name, None)


def get_kind(name):
    try:
        return _registry[name]
    except KeyError:
        raise LookupError(f"Unknown docshelf kind {name!r}") from None


def get_kinds():
    return list(_registry.values())


def get_choices():
    return [(kind.name, kind.label) for kind in _registry.values()]


register(Kind("file", _("File"), target=Kind.FILE, icon="doc"))
register(Kind("link", _("External link"), target=Kind.URL, icon="link"))
register(Kind("form", _("Online form"), target=Kind.URL, icon="form"))

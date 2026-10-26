import pytest

from docshelf import kinds
from docshelf.kinds import Kind


def test_builtin_kinds():
    assert [k.name for k in kinds.get_kinds()][:3] == ["file", "link", "form"]
    assert kinds.get_kind("file").needs_file
    assert not kinds.get_kind("form").needs_file


def test_register_and_unregister_custom_kind():
    kinds.register(Kind("map", "Map", target=Kind.URL))
    try:
        assert ("map", "Map") in kinds.get_choices()
    finally:
        kinds.unregister("map")
    with pytest.raises(LookupError):
        kinds.get_kind("map")


def test_invalid_target_is_rejected():
    with pytest.raises(ValueError):
        Kind("broken", "Broken", target="ftp")

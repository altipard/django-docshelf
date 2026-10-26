from docshelf.checks import check_storage


def test_no_warning_with_docshelf_storage():
    assert check_storage(None) == []


def test_warning_without_docshelf_storage(settings):
    settings.STORAGES = {k: v for k, v in settings.STORAGES.items() if k != "docshelf"}
    assert [m.id for m in check_storage(None)] == ["docshelf.W001"]

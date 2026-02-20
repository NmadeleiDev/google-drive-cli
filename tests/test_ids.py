import pytest

from gdrive_cli.ids import ValidationError, resolve_file_id, resolve_folder_id


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1AbcdefGhIjKlmNop", "1AbcdefGhIjKlmNop"),
        ("https://drive.google.com/drive/folders/1AbcdefGhIjKlmNop", "1AbcdefGhIjKlmNop"),
        ("https://drive.google.com/open?id=1AbcdefGhIjKlmNop", "1AbcdefGhIjKlmNop"),
    ],
)
def test_resolve_folder_id(value, expected):
    assert resolve_folder_id(value) == expected


def test_resolve_folder_defaults_to_root():
    assert resolve_folder_id(None) == "root"


def test_resolve_folder_rejects_file_link():
    with pytest.raises(ValidationError, match="file link"):
        resolve_folder_id("https://drive.google.com/file/d/1AbcdefGhIjKlmNop/view")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1AbcdefGhIjKlmNop", "1AbcdefGhIjKlmNop"),
        ("https://drive.google.com/file/d/1AbcdefGhIjKlmNop/view", "1AbcdefGhIjKlmNop"),
        ("https://docs.google.com/document/d/1AbcdefGhIjKlmNop/edit", "1AbcdefGhIjKlmNop"),
    ],
)
def test_resolve_file_id(value, expected):
    assert resolve_file_id(value) == expected


def test_resolve_file_rejects_folder_link():
    with pytest.raises(ValidationError, match="folder link"):
        resolve_file_id("https://drive.google.com/drive/folders/1AbcdefGhIjKlmNop")


def test_resolve_file_rejects_non_google_url():
    with pytest.raises(ValidationError, match="Google Drive"):
        resolve_file_id("https://example.com/file/d/1AbcdefGhIjKlmNop/view")

"""Drive link and ID parsing utilities."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


class ValidationError(RuntimeError):
    """Raised for invalid user input."""


_DRIVE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_PATH_D_RE = re.compile(r"/d/([A-Za-z0-9_-]{10,})")
_PATH_FILE_D_RE = re.compile(r"/file/d/([A-Za-z0-9_-]{10,})")
_PATH_FOLDER_RE = re.compile(r"/drive/folders/([A-Za-z0-9_-]{10,})")


def resolve_folder_id(value: str | None) -> str:
    """Resolve folder ID from raw ID or Drive folder link. Defaults to root."""
    if value is None:
        return "root"
    return _resolve_drive_id(value=value, expected="folder")


def resolve_file_id(value: str) -> str:
    """Resolve file ID from raw ID or Drive file link."""
    return _resolve_drive_id(value=value, expected="file")


def _resolve_drive_id(*, value: str, expected: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValidationError("Value cannot be empty.")

    if _DRIVE_ID_RE.fullmatch(raw):
        return raw

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValidationError(f"Expected a Google Drive {expected} ID or link.")

    host = parsed.netloc.lower()
    if not host.endswith("google.com"):
        raise ValidationError(f"Expected a Google Drive {expected} link.")

    path = parsed.path
    query = parse_qs(parsed.query)

    if expected == "folder" and "/file/" in path:
        raise ValidationError("Expected folder link/ID, but file link was provided.")
    if expected == "file" and "/folders/" in path:
        raise ValidationError("Expected file link/ID, but folder link was provided.")

    for regex in (_PATH_FOLDER_RE, _PATH_FILE_D_RE, _PATH_D_RE):
        match = regex.search(path)
        if match:
            return match.group(1)

    query_id = query.get("id")
    if query_id and _DRIVE_ID_RE.fullmatch(query_id[0]):
        return query_id[0]

    raise ValidationError(f"Could not extract {expected} ID from value: {value}")

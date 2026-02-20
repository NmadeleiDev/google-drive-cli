"""Google Drive API client helpers."""

from __future__ import annotations

from googleapiclient.discovery import build

from gdrive_cli.auth import load_credentials


def build_drive_service(write: bool = False):
    """Create a Google Drive API service client."""
    credentials = load_credentials(write=write)
    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )

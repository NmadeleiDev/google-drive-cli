"""Filesystem paths used by the CLI."""

from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    env_value = os.environ.get("GDRIVE_CONFIG_DIR")
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".config" / "gdrive-cli"


def credentials_file() -> Path:
    env_value = os.environ.get("GDRIVE_CREDENTIALS_FILE")
    if env_value:
        return Path(env_value).expanduser()
    return config_dir() / "credentials.json"

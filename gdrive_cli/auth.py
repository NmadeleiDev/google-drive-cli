"""Authentication helpers for Google Drive."""

from __future__ import annotations

import json
from pathlib import Path

import google.auth
from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gdrive_cli.paths import credentials_file

READ_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/drive"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class AuthError(RuntimeError):
    """Raised when credentials cannot be loaded or refreshed."""


def login_with_client_secret(
    client_secret_path: str,
    *,
    write: bool = True,
    launch_browser: bool = True,
) -> Path:
    """Run OAuth installed-app flow and persist credential file."""
    scope = WRITE_SCOPE if write else READ_SCOPE

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secret_path,
            scopes=[scope],
        )
        credentials = flow.run_local_server(port=0, open_browser=launch_browser)
    except OSError as exc:
        raise AuthError(f"Could not read client secret file: {client_secret_path}") from exc
    except Exception as exc:  # noqa: BLE001
        raise AuthError(f"OAuth login failed: {exc}") from exc

    path = credentials_file()
    _persist_credentials(credentials, path)
    return path


def load_credentials(write: bool = False):
    """Load credentials, preferring local OAuth token, then ADC fallback."""
    required_scope = WRITE_SCOPE if write else READ_SCOPE

    stored = _load_stored_credentials(required_scope)
    if stored is not None:
        return stored

    return _load_adc_credentials(required_scope)


def stored_credentials_info() -> dict | None:
    """Return metadata about stored credentials if present."""
    path = credentials_file()
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthError(f"Stored credentials are invalid JSON: {path}") from exc

    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list):
        scopes = []

    return {
        "path": str(path),
        "scopes": scopes,
        "has_refresh_token": bool(payload.get("refresh_token")),
        "client_id": payload.get("client_id"),
    }


def _load_stored_credentials(required_scope: str):
    path = credentials_file()
    if not path.exists():
        return None

    try:
        credentials = Credentials.from_authorized_user_file(str(path))
    except Exception as exc:  # noqa: BLE001
        raise AuthError(
            f"Stored credentials at {path} are unreadable. "
            "Run `gdrive auth login --client-secret <path>` again."
        ) from exc

    _validate_scope(credentials.scopes, required_scope)
    return _ensure_valid_credentials(credentials, source_path=path, required_scope=required_scope)


def _load_adc_credentials(required_scope: str):
    try:
        credentials, _ = google.auth.default(scopes=[required_scope])
    except DefaultCredentialsError as exc:
        raise AuthError(_missing_credentials_message(required_scope)) from exc

    return _ensure_valid_credentials(
        credentials,
        source_path=None,
        required_scope=required_scope,
    )


def _ensure_valid_credentials(credentials, source_path: Path | None, required_scope: str):
    if credentials.valid:
        return credentials

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except (RefreshError, TransportError) as exc:
            if source_path:
                raise AuthError(
                    "Stored OAuth credentials could not be refreshed. "
                    "Run `gdrive auth login --client-secret <path>` again."
                ) from exc
            raise AuthError(_refresh_failed_message(required_scope)) from exc

        if source_path:
            _persist_credentials(credentials, source_path)
        return credentials

    if source_path:
        raise AuthError(
            "Stored OAuth credentials are invalid and cannot be refreshed. "
            "Run `gdrive auth login --client-secret <path>` again."
        )

    raise AuthError(_refresh_failed_message(required_scope))


def _persist_credentials(credentials: Credentials, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json() + "\n", encoding="utf-8")


def _validate_scope(granted_scopes: list[str] | None, required_scope: str) -> None:
    if not granted_scopes:
        raise AuthError(
            "Stored credentials missing scopes. "
            "Run `gdrive auth login --client-secret <path>` again."
        )

    scope_set = set(granted_scopes)
    if required_scope == READ_SCOPE and WRITE_SCOPE in scope_set:
        return

    if required_scope in scope_set:
        return

    raise AuthError(
        f"Stored credentials do not include required scope '{required_scope}'. "
        "Run `gdrive auth login --client-secret <path>` again."
    )


def _missing_credentials_message(scope: str) -> str:
    scopes = f"{CLOUD_PLATFORM_SCOPE},{scope}"
    return (
        "No usable credentials found. Preferred setup:\n"
        "gdrive auth login --client-secret <path-to-client-secret.json>\n\n"
        "ADC fallback:\n"
        "gcloud auth application-default login "
        "--client-id-file=<path-to-client-secret.json> "
        f"--scopes={scopes}"
    )


def _refresh_failed_message(scope: str) -> str:
    scopes = f"{CLOUD_PLATFORM_SCOPE},{scope}"
    return (
        "Failed to refresh ADC credentials. Re-run:\n"
        "gcloud auth application-default login "
        "--client-id-file=<path-to-client-secret.json> "
        f"--scopes={scopes}"
    )

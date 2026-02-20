"""Click CLI for Google Drive."""

from __future__ import annotations

import json
import sys
from functools import wraps
from pathlib import Path

import click
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from gdrive_cli import __version__
from gdrive_cli.auth import AuthError, load_credentials, login_with_client_secret, stored_credentials_info
from gdrive_cli.client import build_drive_service
from gdrive_cli.ids import ValidationError, resolve_file_id, resolve_folder_id
from gdrive_cli.output import render_records
from gdrive_cli.paths import credentials_file

USER_INPUT_EXIT_CODE = 2
AUTH_EXIT_CODE = 3
API_EXIT_CODE = 4


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Google Drive CLI."""


def command_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValidationError, ValueError) as exc:
            click.echo(f"Error: {exc}", err=True)
            raise click.exceptions.Exit(USER_INPUT_EXIT_CODE) from exc
        except AuthError as exc:
            click.echo(f"Auth error: {exc}", err=True)
            raise click.exceptions.Exit(AUTH_EXIT_CODE) from exc
        except HttpError as exc:
            status = getattr(exc.resp, "status", "unknown")
            click.echo(f"API error ({status}): {_extract_http_error(exc)}", err=True)
            raise click.exceptions.Exit(API_EXIT_CODE) from exc

    return wrapper


def _extract_http_error(exc: HttpError) -> str:
    content = getattr(exc, "content", None)
    if not content:
        return str(exc)

    try:
        payload = json.loads(content.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return str(exc)

    if isinstance(payload, dict):
        error = payload.get("error", {})
        message = error.get("message")
        if message:
            return message

    return str(exc)


@cli.group()
def auth() -> None:
    """Authenticate and inspect credentials."""


@auth.command("login")
@click.option(
    "--client-secret",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    help="Path to OAuth client secret JSON.",
)
@click.option("--readonly", is_flag=True, help="Request readonly scope only.")
@click.option("--no-launch-browser", is_flag=True, help="Do not auto-open browser.")
@command_errors
def auth_login(client_secret: str, readonly: bool, no_launch_browser: bool) -> None:
    """Run OAuth login and save local credentials."""
    output_path = login_with_client_secret(
        client_secret,
        write=not readonly,
        launch_browser=not no_launch_browser,
    )
    click.echo(f"Saved credentials to {output_path}")


@auth.command("whoami")
@click.option("--output", "output_format", type=click.Choice(["table", "json"]), default="table")
@command_errors
def auth_whoami(output_format: str) -> None:
    """Show locally stored credential details."""
    info = stored_credentials_info()
    if info is None:
        raise ValidationError(
            "No local OAuth credentials found. Run `gdrive auth login --client-secret <path>` first."
        )

    record = {
        "path": info["path"],
        "has_refresh_token": info["has_refresh_token"],
        "scopes": ",".join(info["scopes"]),
        "client_id": info.get("client_id") or "",
    }
    click.echo(render_records([record], output_format=output_format))


@cli.command("doctor")
def doctor() -> None:
    """Run diagnostics for environment, auth, and API connectivity."""
    checks: list[dict] = []
    failures = 0

    checks.append(
        {
            "check": "python",
            "status": "ok",
            "detail": sys.version.split()[0],
        }
    )

    checks.append(
        {
            "check": "credentials-path",
            "status": "ok",
            "detail": str(credentials_file()),
        }
    )

    info = None
    try:
        info = stored_credentials_info()
    except AuthError as exc:
        checks.append(
            {
                "check": "stored-credentials",
                "status": "fail",
                "detail": str(exc),
            }
        )
        failures += 1

    if info is None:
        checks.append(
            {
                "check": "stored-credentials",
                "status": "warn",
                "detail": f"not found at {credentials_file()} (ADC fallback may still work)",
            }
        )
    elif info:
        checks.append(
            {
                "check": "stored-credentials",
                "status": "ok",
                "detail": info["path"],
            }
        )

    try:
        load_credentials(write=False)
        checks.append(
            {
                "check": "auth-refresh",
                "status": "ok",
                "detail": "credentials load and refresh succeeded",
            }
        )
    except AuthError as exc:
        checks.append(
            {
                "check": "auth-refresh",
                "status": "fail",
                "detail": str(exc),
            }
        )
        failures += 1

    try:
        service = build_drive_service(write=False)
        response = service.files().list(pageSize=1, fields="files(id)").execute()
        count = len(response.get("files", []))
        checks.append(
            {
                "check": "api-connectivity",
                "status": "ok",
                "detail": f"files.list succeeded ({count} file(s) sampled)",
            }
        )
    except (AuthError, HttpError, Exception) as exc:  # noqa: BLE001
        checks.append(
            {
                "check": "api-connectivity",
                "status": "fail",
                "detail": str(exc),
            }
        )
        failures += 1

    click.echo(render_records(checks, output_format="table"))
    if failures:
        raise click.exceptions.Exit(1)


@cli.command("ls")
@click.option(
    "--folder",
    "folder_value",
    default=None,
    help="Folder ID or Google Drive folder link. Defaults to root.",
)
@click.option("--output", "output_format", type=click.Choice(["table", "json", "csv"]), default="table")
@click.option("--csv-path", type=click.Path(dir_okay=False, writable=True, path_type=str), default=None)
@command_errors
def list_directory(folder_value: str | None, output_format: str, csv_path: str | None) -> None:
    """List files in a folder."""
    folder_id = resolve_folder_id(folder_value)
    service = build_drive_service(write=False)

    query = f"'{folder_id}' in parents and trashed = false"
    response = (
        service.files()
        .list(
            q=query,
            fields="files(id,name,mimeType,size,modifiedTime,trashed)",
            orderBy="folder,name",
            pageSize=1000,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )

    entries = response.get("files", [])
    records = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "mimeType": item.get("mimeType"),
            "size": item.get("size"),
            "modifiedTime": item.get("modifiedTime"),
            "trashed": item.get("trashed"),
        }
        for item in entries
    ]

    click.echo(render_records(records, output_format=output_format, csv_path=csv_path))


@cli.command("upload")
@click.argument("local_path", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option(
    "--folder",
    "folder_value",
    default=None,
    help="Target folder ID or link. Defaults to root.",
)
@click.option("--output", "output_format", type=click.Choice(["table", "json"]), default="table")
@command_errors
def upload_file(local_path: str, folder_value: str | None, output_format: str) -> None:
    """Upload one local file to Drive."""
    folder_id = resolve_folder_id(folder_value)
    file_name = Path(local_path).name

    metadata: dict[str, object] = {"name": file_name}
    if folder_id != "root":
        metadata["parents"] = [folder_id]

    media = MediaFileUpload(local_path, resumable=True)
    service = build_drive_service(write=True)
    created = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,mimeType,size,webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    if output_format == "json":
        click.echo(render_records([created], output_format="json"))
        return

    click.echo(
        render_records(
            [
                {
                    "id": created.get("id"),
                    "name": created.get("name"),
                    "mimeType": created.get("mimeType"),
                    "size": created.get("size"),
                    "webViewLink": created.get("webViewLink"),
                }
            ],
            output_format="table",
        )
    )


@cli.command("download")
@click.option("--file", "file_value", required=True, help="File ID or Google Drive file link.")
@click.option(
    "--output-path",
    type=click.Path(dir_okay=False, path_type=str),
    default=None,
    help="Local destination path. Defaults to remote file name in current directory.",
)
@command_errors
def download_file(file_value: str, output_path: str | None) -> None:
    """Download one file from Drive."""
    file_id = resolve_file_id(file_value)
    service = build_drive_service(write=False)

    metadata = (
        service.files()
        .get(fileId=file_id, fields="id,name,mimeType,size", supportsAllDrives=True)
        .execute()
    )

    destination = Path(output_path) if output_path else Path(metadata.get("name") or file_id)
    destination.parent.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)

    with destination.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    click.echo(f"Downloaded {metadata.get('name') or file_id} to {destination}")


@cli.command("trash")
@click.option("--file", "file_value", required=True, help="File ID or Google Drive file link.")
@command_errors
def trash_file(file_value: str) -> None:
    """Move a file to trash."""
    file_id = resolve_file_id(file_value)
    service = build_drive_service(write=True)
    item = (
        service.files()
        .update(
            fileId=file_id,
            body={"trashed": True},
            fields="id,name,trashed",
            supportsAllDrives=True,
        )
        .execute()
    )

    click.echo(f"Moved to trash: {item.get('name') or file_id} ({item.get('id')})")

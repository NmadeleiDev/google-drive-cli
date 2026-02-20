from pathlib import Path

from click.testing import CliRunner

from gdrive_cli.auth import AuthError
from gdrive_cli.cli import cli


class ExecuteResult:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def execute(self):
        return self.payload


class FakeFilesResource:
    def __init__(self, list_response=None, create_response=None, get_response=None, update_response=None):
        self.list_response = list_response or {"files": []}
        self.create_response = create_response or {}
        self.get_response = get_response or {}
        self.update_response = update_response or {}

        self.last_list = None
        self.last_create = None
        self.last_get = None
        self.last_get_media = None
        self.last_update = None

    def list(self, **kwargs):
        self.last_list = kwargs
        return ExecuteResult(self.list_response)

    def create(self, **kwargs):
        self.last_create = kwargs
        return ExecuteResult(self.create_response)

    def get(self, **kwargs):
        self.last_get = kwargs
        return ExecuteResult(self.get_response)

    def get_media(self, **kwargs):
        self.last_get_media = kwargs
        return object()

    def update(self, **kwargs):
        self.last_update = kwargs
        return ExecuteResult(self.update_response)


class FakeService:
    def __init__(self, files_resource=None):
        self._files_resource = files_resource or FakeFilesResource()

    def files(self):
        return self._files_resource


class FakeDownloader:
    def __init__(self, handle, request):
        self.handle = handle
        self.request = request
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        self.handle.write(b"hello")
        return None, True


def test_ls_uses_folder_link_and_formats_table(monkeypatch):
    runner = CliRunner()
    files_resource = FakeFilesResource(
        list_response={
            "files": [
                {
                    "id": "abc",
                    "name": "demo.txt",
                    "mimeType": "text/plain",
                    "size": "12",
                    "modifiedTime": "2026-02-20T00:00:00Z",
                    "trashed": False,
                }
            ]
        }
    )
    fake_service = FakeService(files_resource=files_resource)

    monkeypatch.setattr("gdrive_cli.cli.build_drive_service", lambda write=False: fake_service)

    result = runner.invoke(
        cli,
        ["ls", "--folder", "https://drive.google.com/drive/folders/1AbcdefGhIjKlmNop"],
    )

    assert result.exit_code == 0
    assert "demo.txt" in result.output
    assert files_resource.last_list is not None
    assert files_resource.last_list["q"] == "'1AbcdefGhIjKlmNop' in parents and trashed = false"


def test_ls_defaults_to_root(monkeypatch):
    runner = CliRunner()
    files_resource = FakeFilesResource()
    fake_service = FakeService(files_resource=files_resource)

    monkeypatch.setattr("gdrive_cli.cli.build_drive_service", lambda write=False: fake_service)

    result = runner.invoke(cli, ["ls"])

    assert result.exit_code == 0
    assert files_resource.last_list is not None
    assert files_resource.last_list["q"] == "'root' in parents and trashed = false"


def test_upload_uses_write_scope_and_folder_parent(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    local_file = tmp_path / "sample.txt"
    local_file.write_text("hello", encoding="utf-8")

    files_resource = FakeFilesResource(
        create_response={
            "id": "f123",
            "name": "sample.txt",
            "mimeType": "text/plain",
            "size": "5",
            "webViewLink": "https://drive.google.com/file/d/f123/view",
        }
    )
    fake_service = FakeService(files_resource=files_resource)
    write_flags = []

    def fake_builder(write=False):
        write_flags.append(write)
        return fake_service

    monkeypatch.setattr("gdrive_cli.cli.build_drive_service", fake_builder)

    result = runner.invoke(
        cli,
        [
            "upload",
            str(local_file),
            "--folder",
            "https://drive.google.com/drive/folders/1AbcdefGhIjKlmNop",
        ],
    )

    assert result.exit_code == 0
    assert "sample.txt" in result.output
    assert write_flags == [True]
    assert files_resource.last_create is not None
    assert files_resource.last_create["body"]["parents"] == ["1AbcdefGhIjKlmNop"]


def test_download_uses_file_link_and_writes_file(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    files_resource = FakeFilesResource(get_response={"id": "f123", "name": "remote.txt"})
    fake_service = FakeService(files_resource=files_resource)

    monkeypatch.setattr("gdrive_cli.cli.build_drive_service", lambda write=False: fake_service)
    monkeypatch.setattr("gdrive_cli.cli.MediaIoBaseDownload", FakeDownloader)

    output_path = tmp_path / "downloaded.txt"
    result = runner.invoke(
        cli,
        [
            "download",
            "--file",
            "https://drive.google.com/file/d/1AbcdefGhIjKlmNop/view",
            "--output-path",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert output_path.read_bytes() == b"hello"
    assert files_resource.last_get is not None
    assert files_resource.last_get["fileId"] == "1AbcdefGhIjKlmNop"
    assert files_resource.last_get_media is not None
    assert files_resource.last_get_media["fileId"] == "1AbcdefGhIjKlmNop"


def test_download_defaults_to_remote_name(monkeypatch):
    runner = CliRunner()

    with runner.isolated_filesystem():
        files_resource = FakeFilesResource(get_response={"id": "f123", "name": "remote.txt"})
        fake_service = FakeService(files_resource=files_resource)

        monkeypatch.setattr("gdrive_cli.cli.build_drive_service", lambda write=False: fake_service)
        monkeypatch.setattr("gdrive_cli.cli.MediaIoBaseDownload", FakeDownloader)

        result = runner.invoke(cli, ["download", "--file", "1AbcdefGhIjKlmNop"])

        assert result.exit_code == 0
        assert Path("remote.txt").exists()
        assert Path("remote.txt").read_bytes() == b"hello"


def test_trash_uses_write_scope(monkeypatch):
    runner = CliRunner()
    files_resource = FakeFilesResource(update_response={"id": "f123", "name": "demo.txt", "trashed": True})
    fake_service = FakeService(files_resource=files_resource)
    write_flags = []

    def fake_builder(write=False):
        write_flags.append(write)
        return fake_service

    monkeypatch.setattr("gdrive_cli.cli.build_drive_service", fake_builder)

    result = runner.invoke(cli, ["trash", "--file", "1AbcdefGhIjKlmNop"])

    assert result.exit_code == 0
    assert "Moved to trash" in result.output
    assert write_flags == [True]
    assert files_resource.last_update is not None
    assert files_resource.last_update["fileId"] == "1AbcdefGhIjKlmNop"
    assert files_resource.last_update["body"] == {"trashed": True}


def test_auth_login_invokes_helper(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    client_secret = tmp_path / "client_secret.json"
    client_secret.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "gdrive_cli.cli.login_with_client_secret",
        lambda client_secret, write, launch_browser: tmp_path / "credentials.json",
    )

    result = runner.invoke(
        cli,
        [
            "auth",
            "login",
            "--client-secret",
            str(client_secret),
            "--no-launch-browser",
        ],
    )

    assert result.exit_code == 0
    assert "Saved credentials" in result.output


def test_auth_whoami_missing(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("gdrive_cli.cli.stored_credentials_info", lambda: None)

    result = runner.invoke(cli, ["auth", "whoami"])

    assert result.exit_code == 2
    assert "No local OAuth credentials" in result.output


def test_doctor_success(monkeypatch):
    runner = CliRunner()
    files_resource = FakeFilesResource(list_response={"files": [{"id": "a"}]})
    fake_service = FakeService(files_resource=files_resource)

    monkeypatch.setattr(
        "gdrive_cli.cli.stored_credentials_info",
        lambda: {
            "path": "/tmp/creds.json",
            "scopes": ["https://www.googleapis.com/auth/drive"],
            "has_refresh_token": True,
            "client_id": "x",
        },
    )
    monkeypatch.setattr("gdrive_cli.cli.load_credentials", lambda write=False: object())
    monkeypatch.setattr("gdrive_cli.cli.build_drive_service", lambda write=False: fake_service)

    result = runner.invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "api-connectivity" in result.output
    assert "files.list succeeded" in result.output


def test_doctor_failure(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr("gdrive_cli.cli.stored_credentials_info", lambda: None)

    def fail_load(write=False):
        raise AuthError("bad creds")

    monkeypatch.setattr("gdrive_cli.cli.load_credentials", fail_load)
    monkeypatch.setattr(
        "gdrive_cli.cli.build_drive_service",
        lambda write=False: (_ for _ in ()).throw(RuntimeError("no network")),
    )

    result = runner.invoke(cli, ["doctor"])

    assert result.exit_code == 1
    assert "auth-refresh" in result.output
    assert "bad creds" in result.output

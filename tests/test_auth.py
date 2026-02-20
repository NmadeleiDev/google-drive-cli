import json

import pytest
from google.auth.exceptions import DefaultCredentialsError

from gdrive_cli.auth import AuthError, READ_SCOPE, WRITE_SCOPE, load_credentials, login_with_client_secret, stored_credentials_info
from gdrive_cli.paths import credentials_file


class FakeCredentials:
    def __init__(self, valid=True, expired=False, refresh_token=False):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token

    def refresh(self, _request):
        self.valid = True


def test_load_credentials_prefers_stored(monkeypatch):
    stored = FakeCredentials(valid=True)

    monkeypatch.setattr("gdrive_cli.auth._load_stored_credentials", lambda required_scope: stored)
    monkeypatch.setattr(
        "gdrive_cli.auth._load_adc_credentials",
        lambda required_scope: pytest.fail("ADC should not be called"),
    )

    creds = load_credentials(write=False)
    assert creds is stored


def test_load_credentials_falls_back_to_adc(monkeypatch):
    adc = FakeCredentials(valid=True)

    monkeypatch.setattr("gdrive_cli.auth._load_stored_credentials", lambda required_scope: None)
    monkeypatch.setattr("gdrive_cli.auth._load_adc_credentials", lambda required_scope: adc)

    creds = load_credentials(write=True)
    assert creds is adc


def test_adc_scope_read(monkeypatch):
    seen = {}

    def fake_default(scopes):
        seen["scopes"] = scopes
        return FakeCredentials(valid=True), "project"

    monkeypatch.setattr("gdrive_cli.auth._load_stored_credentials", lambda required_scope: None)
    monkeypatch.setattr("gdrive_cli.auth.google.auth.default", fake_default)

    creds = load_credentials(write=False)
    assert seen["scopes"] == [READ_SCOPE]
    assert creds.valid


def test_adc_scope_write(monkeypatch):
    seen = {}

    def fake_default(scopes):
        seen["scopes"] = scopes
        return FakeCredentials(valid=True), "project"

    monkeypatch.setattr("gdrive_cli.auth._load_stored_credentials", lambda required_scope: None)
    monkeypatch.setattr("gdrive_cli.auth.google.auth.default", fake_default)

    creds = load_credentials(write=True)
    assert seen["scopes"] == [WRITE_SCOPE]
    assert creds.valid


def test_load_credentials_missing(monkeypatch):
    monkeypatch.setattr("gdrive_cli.auth._load_stored_credentials", lambda required_scope: None)

    def fake_default(scopes):
        raise DefaultCredentialsError("missing")

    monkeypatch.setattr("gdrive_cli.auth.google.auth.default", fake_default)

    with pytest.raises(AuthError, match="No usable credentials found"):
        load_credentials(write=False)


def test_stored_credentials_info_reads_file():
    path = credentials_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "refresh_token": "x",
                "client_id": "abc",
                "scopes": [WRITE_SCOPE],
            }
        ),
        encoding="utf-8",
    )

    info = stored_credentials_info()

    assert info is not None
    assert info["path"] == str(path)
    assert info["has_refresh_token"] is True
    assert info["scopes"] == [WRITE_SCOPE]
    assert info["client_id"] == "abc"


def test_login_with_client_secret_writes_token(monkeypatch, tmp_path):
    client_secret_path = tmp_path / "client_secret.json"
    client_secret_path.write_text("{}", encoding="utf-8")

    class FakeFlow:
        def run_local_server(self, port, open_browser):
            class Creds:
                def to_json(self):
                    return '{"refresh_token":"r","scopes":["https://www.googleapis.com/auth/drive"]}'

            assert port == 0
            assert open_browser is False
            return Creds()

    monkeypatch.setattr(
        "gdrive_cli.auth.InstalledAppFlow.from_client_secrets_file",
        lambda path, scopes: FakeFlow(),
    )

    output = login_with_client_secret(
        str(client_secret_path),
        write=True,
        launch_browser=False,
    )

    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["refresh_token"] == "r"

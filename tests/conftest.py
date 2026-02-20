import pytest


@pytest.fixture(autouse=True)
def isolate_user_files(tmp_path, monkeypatch):
    config_dir = tmp_path / "gdrive-cli"
    monkeypatch.setenv("GDRIVE_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("GDRIVE_CREDENTIALS_FILE", str(config_dir / "credentials.json"))

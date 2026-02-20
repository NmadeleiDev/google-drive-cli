# google-drive-cli-for-agents

CLI for Google Drive using the official Google API Python client.

## Features
- OAuth login without mandatory `gcloud`
- `pipx`-friendly install (`gdrive` available globally)
- List folder contents via folder ID or folder link
- Upload local files to a folder via folder ID or folder link
- Download files via file ID or file link
- Move files to trash via file ID or file link
- Diagnostics with `gdrive doctor`

## Install (Recommended)

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install google-drive-cli-for-agents
```

Verify:

```bash
gdrive --version
```

Upgrade:

```bash
pipx upgrade google-drive-cli-for-agents
```

## Install From Source

Local development:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install via pipx from local clone:

```bash
pipx install -e /absolute/path/to/google-drive-cli
```

## OAuth Setup

Create a Google OAuth client of type **Desktop app**, then run:

```bash
gdrive auth login --client-secret /absolute/path/to/client_secret.json
```

Readonly token:

```bash
gdrive auth login --readonly --client-secret /absolute/path/to/client_secret.json
```

Inspect local credentials:

```bash
gdrive auth whoami
gdrive doctor
```

## Usage

List a folder (or root if omitted):

```bash
gdrive ls --folder https://drive.google.com/drive/folders/<folder-id>
gdrive ls --folder <folder-id>
gdrive ls
```

Upload a file:

```bash
gdrive upload ./report.csv --folder <folder-id>
gdrive upload ./report.csv --folder https://drive.google.com/drive/folders/<folder-id>
```

Download a file:

```bash
gdrive download --file <file-id>
gdrive download --file https://drive.google.com/file/d/<file-id>/view --output-path ./report.csv
```

Move a file to trash:

```bash
gdrive trash --file <file-id>
gdrive trash --file https://drive.google.com/file/d/<file-id>/view
```

## Output Formats

`gdrive ls` supports:
- `--output table` (default)
- `--output json`
- `--output csv --csv-path ./files.csv`

`gdrive upload` supports:
- `--output table` (default)
- `--output json`

## Credentials Path

By default credentials are stored at:
- `~/.config/gdrive-cli/credentials.json`

Override with env vars:
- `GDRIVE_CONFIG_DIR`
- `GDRIVE_CREDENTIALS_FILE`

## ADC Fallback (Optional)

If preferred, ADC via `gcloud` still works:

```bash
gcloud auth application-default login \
  --client-id-file=/absolute/path/to/client_secret.json \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive
```

## Publishing

Build artifacts:

```bash
python -m build
```

Upload manually:

```bash
python -m twine upload dist/*
```

# Google Drive CLI Plan

## Goal
Build a pipx-installable Python CLI for Google Drive with:
- List directory contents by folder link or folder ID.
- Upload file to a folder by folder link or folder ID.
- Download file by file link or file ID.
- Move file to trash by file link or file ID.

## Implementation Checklist
- [x] Scaffold package structure and packaging metadata (`pyproject.toml`, module layout, entrypoint).
- [x] Implement path/config helpers and auth flow (OAuth login with client secret + stored credentials + ADC fallback).
- [x] Implement Drive service client builder.
- [x] Implement ID/link parsing utilities for folders/files.
- [x] Implement CLI commands: `auth login`, `auth whoami`, `ls`, `upload`, `download`, `trash`, `doctor`.
- [x] Implement output rendering (`table`, `json`, `csv`) for list output.
- [x] Add robust unit tests for parsing, config/auth behavior, output rendering.
- [x] Add CLI tests for all core commands and error handling with mocked API service.
- [x] Run full test suite and fix all issues.
- [x] Build sdist/wheel and verify package artifacts for pipx installability.
- [x] Update README with setup, auth, examples, and publishing/install instructions.

## Verification Checklist
- [x] `pytest` passes locally.
- [x] `python -m build` succeeds.
- [x] `pipx install -e .` command documented and expected entrypoint confirmed.

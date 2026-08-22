"""infrastructure/local_storage/settings_store.py — Settings local-disk persistence
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Local-disk I/O for reading and writing settings JSON files. No network calls,
no print().
"""

# mypy: ignore-errors

import json
from pathlib import Path

from domain.settings import LOCAL_SETTINGS, PROJECT_SETTINGS, USER_SETTINGS, _read_json


def write_setting(scope: str, key: str, value) -> Path:
    path = {"user": USER_SETTINGS, "project": PROJECT_SETTINGS, "local": LOCAL_SETTINGS}[scope]
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_json(path)
    data[key] = value
    path.write_text(json.dumps(data, indent=2))
    return path


def read_all_settings() -> dict:
    return _read_json(USER_SETTINGS), _read_json(PROJECT_SETTINGS), _read_json(LOCAL_SETTINGS)

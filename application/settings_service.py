"""application/settings_service.py — use-case layer for Settings
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/settings.py + infrastructure/local_storage/settings_store.py
— no print() of its own.
"""

from pathlib import Path

from domain.settings import (
    load_settings,
    load_settings_with_provenance,
    render_status_line,
)
from infrastructure.local_storage.settings_store import write_setting


def get_merged_settings(cli_overrides: dict | None = None) -> dict:
    return load_settings(cli_overrides)


def get_settings_with_provenance() -> dict:
    return load_settings_with_provenance()


def update_setting(scope: str, key: str, value) -> Path:
    return write_setting(scope, key, value)


def render_status_line_text(session_state: dict, settings: dict | None = None) -> str:
    sl = (settings or load_settings()).get("statusLine", {})
    command = sl.get("command") if isinstance(sl, dict) else None
    return render_status_line(session_state, command)

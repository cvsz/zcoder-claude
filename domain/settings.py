"""domain/settings.py — Settings domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for settings management and status line rendering.
No I/O, no print() — those belong to infrastructure/ and interfaces/.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional

USER_SETTINGS = Path("~/.claude/settings.json").expanduser()
PROJECT_SETTINGS = Path(".claude/settings.json")
LOCAL_SETTINGS = Path(".claude/settings.local.json")

DEFAULT_STATUS_LINE_TEMPLATE = "[{model}] {cwd} · turns:{turns} · ${cost}"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(cli_overrides: Optional[dict] = None) -> dict:
    merged = {}
    for path in (USER_SETTINGS, PROJECT_SETTINGS, LOCAL_SETTINGS):
        merged = _deep_merge(merged, _read_json(path))
    if cli_overrides:
        merged = _deep_merge(merged, {k: v for k, v in cli_overrides.items() if v is not None})
    return merged


def load_settings_with_provenance() -> dict:
    layers = [
        ("user", _read_json(USER_SETTINGS)),
        ("project", _read_json(PROJECT_SETTINGS)),
        ("local", _read_json(LOCAL_SETTINGS)),
    ]
    merged, provenance = {}, {}
    for layer_name, data in layers:
        merged = _deep_merge(merged, data)
        for k in data:
            provenance[k] = layer_name
    return {"settings": merged, "provenance": provenance}


def render_status_line(session_state: dict, status_line_command: Optional[str] = None) -> str:
    if status_line_command:
        try:
            r = subprocess.run(
                status_line_command, shell=True,
                input=json.dumps(session_state),
                capture_output=True, text=True, timeout=5,
            )
            line = r.stdout.strip()
            if line:
                return line
        except Exception as e:
            return f"[statusLine error: {e}]"

    template = DEFAULT_STATUS_LINE_TEMPLATE
    return template.format(
        model=session_state.get("model", "?"),
        cwd=session_state.get("cwd", "?"),
        turns=session_state.get("turns", "?"),
        cost=session_state.get("cost", "0.00"),
    )

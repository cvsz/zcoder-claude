"""
claude_settings.py — Settings precedence & statusLine (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (153 lines: settings
merge, statusLine renderer, and 2 cmd_* CLI entry points). It has been split
into:

  domain/settings.py                                      — _read_json, _deep_merge,
                                                            load_settings(),
                                                            load_settings_with_provenance(),
                                                            render_status_line()
  infrastructure/local_storage/settings_store.py          — write_setting()
  application/settings_service.py                         — use-case layer
  interfaces/cli/commands/settings_commands.py            — print(), cmd_settings_show,
                                                            cmd_status_line

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.settings import (
    USER_SETTINGS, PROJECT_SETTINGS, LOCAL_SETTINGS,
    DEFAULT_STATUS_LINE_TEMPLATE,
    _read_json, _deep_merge,
    load_settings, load_settings_with_provenance, render_status_line,
)
from infrastructure.local_storage.settings_store import write_setting
from interfaces.cli.commands.settings_commands import (
    cmd_settings_show, cmd_status_line,
)

__all__ = [
    "USER_SETTINGS", "PROJECT_SETTINGS", "LOCAL_SETTINGS",
    "DEFAULT_STATUS_LINE_TEMPLATE",
    "_read_json", "_deep_merge",
    "load_settings", "load_settings_with_provenance", "render_status_line",
    "write_setting",
    "cmd_settings_show", "cmd_status_line",
]

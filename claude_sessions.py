"""
claude_sessions.py — Persistent conversation sessions (compatibility shim)
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

This module used to contain the full implementation (227 lines: the
Turn/Session/Checkpoint dataclasses, storage helpers, away_summary(),
and 4 cmd_* CLI entry points). It has been split into:

  domain/sessions.py                              — pure dataclasses
  infrastructure/local_storage/sessions_store.py   — persistence +
                                                      away_summary()
  application/sessions_service.py                  — use-case layer
  interfaces/cli/commands/sessions_commands.py     — print(), the 4
                                                      cmd_* entry points

This file re-exports every name the old module used to export, so
existing imports (`from claude_sessions import cmd_sessions_list`,
etc., used by main.py) keep working unmodified. See exec-planning.md
§5 (migration playbook).
"""

from domain.sessions import SKIP_DIRS, Checkpoint, Session, Turn
from infrastructure.local_storage.sessions_store import (
    CHECKPOINTS_DIR,
    SESSIONS_DIR,
    away_summary,
    capture_checkpoint,
    latest_session,
    list_checkpoints,
    list_sessions,
    load_session,
    rewind_to_checkpoint,
    save_session,
)
from interfaces.cli.commands.sessions_commands import (
    cmd_away_summary,
    cmd_checkpoint_list,
    cmd_session_show,
    cmd_sessions_list,
)

__all__ = [
    "Turn",
    "Session",
    "Checkpoint",
    "SKIP_DIRS",
    "SESSIONS_DIR",
    "CHECKPOINTS_DIR",
    "save_session",
    "load_session",
    "latest_session",
    "list_sessions",
    "capture_checkpoint",
    "rewind_to_checkpoint",
    "list_checkpoints",
    "away_summary",
    "cmd_sessions_list",
    "cmd_session_show",
    "cmd_checkpoint_list",
    "cmd_away_summary",
]

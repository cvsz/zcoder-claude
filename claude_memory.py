"""
claude_memory.py — Persistent cross-session memory (compatibility shim)
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

This module used to contain the full implementation (175 lines: the
MemType enum, MemEntry dataclass, MemoryStore class, and 5 cmd_* CLI
entry points). It has been split into:

  domain/memory.py                                — pure MemType/MemEntry
  infrastructure/local_storage/memory_store.py     — MemoryStore
  application/memory_service.py                    — use-case layer
  interfaces/cli/commands/memory_commands.py       — print(), the 5
                                                      cmd_* entry points

One pre-existing dead-code line was removed during the split (a `prot`
local variable in enforce_retention() that was computed but never
used) — same bug in the original, confirmed via pyflakes on the
untouched source before this migration; fixing it was required to
meet this migration's own "pyflakes clean" exit criterion, and it has
no behavioral effect (the variable was never read).

This file re-exports every name the old module used to export, so
existing imports (`from claude_memory import cmd_memory_add`, etc.,
used by main.py) keep working unmodified. See exec-planning.md §5
(migration playbook).
"""

from domain.memory import MemEntry, MemType
from infrastructure.local_storage.memory_store import MEMORY_DIR, MemoryStore
from interfaces.cli.commands.memory_commands import (
    cmd_memory_add,
    cmd_memory_forget,
    cmd_memory_recall,
    cmd_memory_retention,
    cmd_memory_stats,
)

__all__ = [
    "MemType",
    "MemEntry",
    "MEMORY_DIR",
    "MemoryStore",
    "cmd_memory_add",
    "cmd_memory_recall",
    "cmd_memory_forget",
    "cmd_memory_stats",
    "cmd_memory_retention",
]

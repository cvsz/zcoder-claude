"""
claude_files.py — Files API (beta) (compatibility shim)
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

This module used to contain the full implementation (367 lines: the
FilesAPI class plus 5 cmd_* CLI entry points). It has been split into:

  domain/files.py                                   — pure validation logic,
                                                        BETA_HEADER
  infrastructure/local_storage/files_registry_store.py — local-disk
                                                        "which files did I
                                                        upload" cache
  infrastructure/anthropic_api/files_gateway.py      — FilesAPI (real HTTP)
  application/files_service.py                       — use-case layer
  interfaces/cli/commands/files_commands.py          — print(), the 5
                                                        cmd_* entry points

This file re-exports every name the old module used to export, so
existing imports (`from claude_files import FilesAPI`, used by
claude_powerpoint.py, claude_excel.py, and application/agents_service.py;
`from claude_files import cmd_file_*`, used by main.py) keep working
unmodified. See exec-planning.md §5 (migration playbook).
"""

from domain.files import (
    _FORBIDDEN_FILENAME_CHARS,
    BETA_HEADER,
    MAX_FILE_SIZE_BYTES,
    _validate_filename,
)
from infrastructure.anthropic_api.files_gateway import FILES_BASE, MESSAGES_BASE, FilesAPI
from infrastructure.local_storage.files_registry_store import LOCAL_REGISTRY
from interfaces.cli.commands.files_commands import (
    cmd_file_ask,
    cmd_file_delete,
    cmd_file_download,
    cmd_file_list,
    cmd_file_upload,
)

__all__ = [
    "BETA_HEADER",
    "MAX_FILE_SIZE_BYTES",
    "_FORBIDDEN_FILENAME_CHARS",
    "_validate_filename",
    "LOCAL_REGISTRY",
    "FILES_BASE",
    "MESSAGES_BASE",
    "FilesAPI",
    "cmd_file_upload",
    "cmd_file_list",
    "cmd_file_delete",
    "cmd_file_ask",
    "cmd_file_download",
]

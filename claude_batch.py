"""
claude_batch.py — Messages Batch API (compatibility shim)
AI Model Coder CLI v1.52.0 (Clean Architecture refactor, Phase C, Context #4)

This module used to contain the full implementation (295 lines: the
BatchCoder class plus 6 cmd_* CLI entry points). It has been split into:

  domain/batch.py                                    — pure feature-flag
                                                        constants
                                                        (OUTPUT_300K_BETA,
                                                        OUTPUT_300K_MODELS,
                                                        OUTPUT_300K_MAX_TOKENS)
  infrastructure/local_storage/batch_store.py        — local-disk
                                                        submission-metadata
                                                        cache
  infrastructure/anthropic_api/batch_gateway.py      — BatchCoder (real
                                                        anthropic SDK calls)
  application/batch_service.py                       — use-case layer
  interfaces/cli/commands/batch_commands.py          — print(), the 6
                                                        cmd_* entry points

This file re-exports every name the old module used to export, so
existing imports (`from claude_batch import cmd_batch_*`, used by
main.py) keep working unmodified. See exec-planning.md §5 (migration
playbook).
"""

from domain.batch import OUTPUT_300K_BETA, OUTPUT_300K_MODELS, OUTPUT_300K_MAX_TOKENS
from infrastructure.local_storage.batch_store import BATCH_STORE
from infrastructure.anthropic_api.batch_gateway import BatchCoder
from interfaces.cli.commands.batch_commands import (
    cmd_batch_submit, cmd_batch_status, cmd_batch_results, cmd_batch_list,
    cmd_batch_cancel, cmd_batch_generate,
)

__all__ = [
    "OUTPUT_300K_BETA", "OUTPUT_300K_MODELS", "OUTPUT_300K_MAX_TOKENS",
    "BATCH_STORE", "BatchCoder",
    "cmd_batch_submit", "cmd_batch_status", "cmd_batch_results",
    "cmd_batch_list", "cmd_batch_cancel", "cmd_batch_generate",
]

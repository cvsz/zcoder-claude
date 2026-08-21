"""
claude_prompt_optimizer.py — Prompt Optimizer & A/B Tester (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (184 lines: optimize,
score, ab_test, prompt library, and 4 cmd_* CLI entry points). It has been
split into:

  domain/prompt_optimizer.py                             — optimize_prompt(),
                                                           score_prompt(),
                                                           ab_test_prompts(),
                                                           parse_score(),
                                                           parse_judgment(),
                                                           PROMPT_LIB_PATH,
                                                           load_lib(), save_lib(),
                                                           lib_add_entry(), etc.
  infrastructure/local_storage/prompt_library_store.py   — read_prompt_lib(),
                                                           write_prompt_lib()
  application/prompt_optimizer_service.py                — use-case layer
  interfaces/cli/commands/prompt_optimizer_commands.py   — print(), cmd_optimize,
                                                           cmd_score, cmd_ab_test,
                                                           cmd_prompt_lib_list

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.prompt_optimizer import (
    PROMPT_LIB_PATH,
    ab_test_prompts,
    lib_add_entry,
    lib_get_entry,
    lib_list_entries,
    load_lib,
    optimize_prompt,
    parse_judgment,
    parse_score,
    save_lib,
    score_prompt,
)
from infrastructure.local_storage.prompt_library_store import (
    read_prompt_lib,
    write_prompt_lib,
)
from interfaces.cli.commands.prompt_optimizer_commands import (
    cmd_ab_test,
    cmd_optimize,
    cmd_prompt_lib_list,
    cmd_score,
)

__all__ = [
    "PROMPT_LIB_PATH",
    "optimize_prompt",
    "score_prompt",
    "ab_test_prompts",
    "parse_score",
    "parse_judgment",
    "load_lib",
    "save_lib",
    "lib_add",
    "lib_list",
    "lib_get",
    "read_prompt_lib",
    "write_prompt_lib",
    "cmd_optimize",
    "cmd_score",
    "cmd_ab_test",
    "cmd_prompt_lib_list",
]

lib_add = lib_add_entry
lib_list = lib_list_entries
lib_get = lib_get_entry

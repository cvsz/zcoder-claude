"""
claude_git.py — AI-powered git integration (compatibility shim)
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

This module used to contain the full implementation (118 lines: SYS
prompt, `_git()` subprocess wrapper, `_call()`, 5 core functions, and 5
cmd_* CLI entry points). It has been split into:

  domain/devtools.py                                    — GIT_SYSTEM_PROMPT
                                                           (was SYS) and the
                                                           5 pure prompt-
                                                           building functions
  infrastructure/local_storage/devtools_store.py         — run_git() (was
                                                           _git()), plus the
                                                           git-log/diff/blame
                                                           subprocess
                                                           compositions and
                                                           the local file
                                                           read/write bits
  infrastructure/anthropic_api/devtools_gateway.py       — git_generate()
                                                           (was _call())
  application/devtools_service.py                        — use-case layer
  interfaces/cli/commands/devtools_commands.py           — print(), the 5
                                                           cmd_* entry points

This file re-exports every name the old module used to export, so
existing imports (`from claude_git import cmd_git_commit`, etc., used by
main.py) keep working unmodified. See exec-planning.md §5 (migration
playbook).
"""

from application.devtools_service import (
    changelog,
    commit_message,
    diff_review,
    explain_blame,
    pr_description,
    staged_diff,
)
from domain.devtools import GIT_SYSTEM_PROMPT as SYS
from infrastructure.anthropic_api.devtools_gateway import git_generate as _call
from infrastructure.local_storage.devtools_store import run_git as _git
from interfaces.cli.commands.devtools_commands import (
    cmd_git_blame_explain,
    cmd_git_changelog,
    cmd_git_commit,
    cmd_git_pr,
    cmd_git_review,
)

__all__ = [
    "SYS",
    "_git",
    "_call",
    "staged_diff",
    "commit_message",
    "pr_description",
    "changelog",
    "diff_review",
    "explain_blame",
    "cmd_git_commit",
    "cmd_git_pr",
    "cmd_git_changelog",
    "cmd_git_review",
    "cmd_git_blame_explain",
]

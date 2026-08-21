"""
claude_github.py — GitHub Integration (compatibility shim)
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

This module used to contain the full implementation (186 lines: GitHub
REST client with retry/circuit-breaking, `_call()` for the anthropic
half, 4 core functions, and 4 cmd_* CLI entry points). It has been split
into:

  domain/devtools.py                                    — the 4 GitHub
                                                           system prompts
                                                           and 4 pure
                                                           context-building
                                                           functions
  infrastructure/github_api/github_gateway.py            — GITHUB_API,
                                                           resolve_token()
                                                           (was _gh_token()),
                                                           get() (was
                                                           _gh_get()),
                                                           fetch_diff() (was
                                                           _gh_fetch_diff()) —
                                                           in its own
                                                           package since
                                                           GitHub is a
                                                           separate vendor,
                                                           same reasoning as
                                                           infrastructure/
                                                           voyage_api/
  infrastructure/anthropic_api/devtools_gateway.py       — github_generate()
                                                           (was _call())
  application/devtools_service.py                        — use-case layer
  interfaces/cli/commands/devtools_commands.py           — print(), the 4
                                                           cmd_* entry points

Two functions' original signatures took a pre-built `anthropic.Anthropic`
client (`_call(client, model, ...)`, and `review_pr`/`triage_issues`/
`summarise_commits`/`generate_pr_description` all took `client` too); the
new `application/devtools_service.py` functions take `api_key` instead
and build the client internally in the gateway, matching every other
gateway in this refactor. Only `cmd_*` signatures are load-bearing for
back-compat (main.py calls those), and those are unchanged.

This file re-exports every name the old module used to export, so
existing imports (`from claude_github import cmd_gh_review_pr`, etc.,
used by main.py) keep working unmodified. See exec-planning.md §5
(migration playbook).
"""

from application.devtools_service import (
    generate_pr_description_gh as generate_pr_description,
)
from application.devtools_service import (
    review_pr,
    summarise_commits,
    triage_issues,
)
from infrastructure.anthropic_api.devtools_gateway import github_generate as _call
from infrastructure.github_api.github_gateway import (
    GITHUB_API,
)
from infrastructure.github_api.github_gateway import (
    fetch_diff as _gh_fetch_diff,
)
from infrastructure.github_api.github_gateway import (
    get as _gh_get,
)
from infrastructure.github_api.github_gateway import (
    resolve_token as _gh_token,
)
from interfaces.cli.commands.devtools_commands import (
    cmd_gh_commits,
    cmd_gh_pr_description,
    cmd_gh_review_pr,
    cmd_gh_triage,
)

__all__ = [
    "GITHUB_API",
    "_gh_token",
    "_gh_get",
    "_gh_fetch_diff",
    "_call",
    "review_pr",
    "triage_issues",
    "summarise_commits",
    "generate_pr_description",
    "cmd_gh_review_pr",
    "cmd_gh_triage",
    "cmd_gh_commits",
    "cmd_gh_pr_description",
]

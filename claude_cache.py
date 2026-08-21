"""
claude_cache.py — Prompt Caching (compatibility shim)
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

This module used to contain the full implementation (553 lines: the
mid-conversation system message helpers, CachingCoder class, and 3
cmd_* CLI entry points). It has been split into:

  domain/cache.py                                 — pure constants,
                                                     SystemMessagePlacementError,
                                                     build_mid_system_message(),
                                                     validate_system_message_placement(),
                                                     cache_control breakpoint helpers
  infrastructure/anthropic_api/cache_gateway.py    — CachingCoder (real HTTP)
  application/cache_service.py                     — use-case layer
  interfaces/cli/commands/cache_commands.py        — print(), the 3
                                                      cmd_* entry points

One behavioral note: the original CachingCoder.print_cache_stats()
method (a print()-emitting method on the gateway class) is gone —
cache_stats() (the pure, dict-returning half) stays on CachingCoder;
the print formatting moved to interfaces/cli/commands/
cache_commands.py's _print_cache_stats(). Confirmed via a repo-wide
grep before removing it that nothing outside this module's own 3
cmd_* functions ever called .print_cache_stats() directly, so this
isn't a back-compat break in practice — but note it here since it IS
a shrink of CachingCoder's public method surface versus the original,
unlike every other re-export in this shim.

This file re-exports every other name the old module used to export,
so existing imports (`from claude_cache import CachingCoder`, etc.,
used by main.py and tests/test_claude_cache.py) keep working
unmodified. See exec-planning.md §5 (migration playbook).
"""

from domain.cache import (
    MID_SYSTEM_SUPPORTED_MODELS,
    SystemMessagePlacementError,
    build_mid_system_message,
    validate_system_message_placement,
)
from domain.cache import (
    add_cache_breakpoint as _add_cache_breakpoint,
)
from domain.cache import (
    make_cache_control as _make_cache_control,
)
from infrastructure.anthropic_api.cache_gateway import CachingCoder
from interfaces.cli.commands.cache_commands import (
    cmd_cache_generate,
    cmd_cache_multi_turn,
    cmd_cache_warm,
)

__all__ = [
    "MID_SYSTEM_SUPPORTED_MODELS",
    "SystemMessagePlacementError",
    "build_mid_system_message",
    "validate_system_message_placement",
    "_make_cache_control",
    "_add_cache_breakpoint",
    "CachingCoder",
    "cmd_cache_generate",
    "cmd_cache_multi_turn",
    "cmd_cache_warm",
]

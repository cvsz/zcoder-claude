"""
claude_fable5.py — Claude Fable 5 / Claude Mythos 5 support (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Real implementation moved 2026-08-21:
  - MESSAGES_ENDPOINT, FABLE5_MODEL_ID, MYTHOS5_MODEL_ID,
    FALLBACK_CREDIT_BETA_HEADER, SERVER_SIDE_FALLBACK_DEFAULT_BETA_HEADER,
    REFUSAL_CATEGORIES, FABLE_MYTHOS_INFO, RefusalError,
    estimate_cost_usd, parse_fallback_chain
    → domain/model_wrappers.py
  - Fable5Client
    → infrastructure/anthropic_api/model_wrappers_gateway.py
  - cmd_fable5_info, cmd_fable5_call
    → interfaces/cli/commands/wrapper_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.model_wrappers import (
    FABLE5_MODEL_ID,
    FABLE_MYTHOS_INFO,
    FALLBACK_CREDIT_BETA_HEADER,
    MESSAGES_ENDPOINT,
    MYTHOS5_MODEL_ID,
    REFUSAL_CATEGORIES,
    SERVER_SIDE_FALLBACK_DEFAULT_BETA_HEADER,
    RefusalError,
    parse_fallback_chain,
)
from domain.model_wrappers import (
    estimate_fable_mythos_cost_usd as estimate_cost_usd,
)
from infrastructure.anthropic_api.model_wrappers_gateway import Fable5Client
from interfaces.cli.commands.wrapper_commands import cmd_fable5_call, cmd_fable5_info

__all__ = [
    "MESSAGES_ENDPOINT",
    "FABLE5_MODEL_ID",
    "MYTHOS5_MODEL_ID",
    "FALLBACK_CREDIT_BETA_HEADER",
    "SERVER_SIDE_FALLBACK_DEFAULT_BETA_HEADER",
    "REFUSAL_CATEGORIES",
    "FABLE_MYTHOS_INFO",
    "RefusalError",
    "Fable5Client",
    "estimate_cost_usd",
    "parse_fallback_chain",
    "cmd_fable5_info",
    "cmd_fable5_call",
]

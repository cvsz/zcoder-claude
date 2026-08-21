"""
claude_opus5.py — Claude Opus 5 support (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Real implementation moved 2026-08-21:
  - MESSAGES_ENDPOINT, OPUS5_MODEL_ID, OPUS5_EFFORT_BUDGETS,
    OPUS5_EFFORT_LEVELS, OPUS5_THINKING_DISABLE_ALLOWED, OPUS5_INFO,
    validate_effort_thinking, validate_inference_geo (now
    validate_opus5_inference_geo — the shared domain module also hosts
    Haiku 4.5's same-named but model-specific validator),
    estimate_cost_usd (now estimate_opus5_cost_usd)
    → domain/model_wrappers.py
  - Opus5Client → infrastructure/anthropic_api/model_wrappers_gateway.py
  - cmd_opus5_info, cmd_opus5_call
              → interfaces/cli/commands/wrapper_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.model_wrappers import (
    MESSAGES_ENDPOINT,
    OPUS5_EFFORT_BUDGETS,
    OPUS5_EFFORT_LEVELS,
    OPUS5_INFO,
    OPUS5_MODEL_ID,
    OPUS5_THINKING_DISABLE_ALLOWED,
    validate_effort_thinking,
)
from domain.model_wrappers import (
    estimate_opus5_cost_usd as estimate_cost_usd,
)
from domain.model_wrappers import (
    validate_opus5_inference_geo as validate_inference_geo,
)
from infrastructure.anthropic_api.model_wrappers_gateway import Opus5Client
from interfaces.cli.commands.wrapper_commands import cmd_opus5_call, cmd_opus5_info

__all__ = [
    "MESSAGES_ENDPOINT",
    "OPUS5_MODEL_ID",
    "OPUS5_EFFORT_BUDGETS",
    "OPUS5_EFFORT_LEVELS",
    "OPUS5_THINKING_DISABLE_ALLOWED",
    "OPUS5_INFO",
    "validate_effort_thinking",
    "validate_inference_geo",
    "Opus5Client",
    "estimate_cost_usd",
    "cmd_opus5_info",
    "cmd_opus5_call",
]

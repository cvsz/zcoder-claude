"""
claude_haiku45.py — Claude Haiku 4.5 support (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Real implementation moved 2026-08-21:
  - MESSAGES_ENDPOINT, HAIKU45_MODEL_ID, HAIKU45_ALIAS,
    MIN_THINKING_BUDGET, HAIKU45_INFO, resolve_model_id,
    build_thinking_param, validate_fast_mode, validate_inference_geo
    (now validate_haiku45_inference_geo — the shared domain module also
    hosts Opus 5's same-named but model-specific validator),
    estimate_cost_usd (now estimate_haiku45_cost_usd)
    → domain/model_wrappers.py
  - Haiku45Client → infrastructure/anthropic_api/model_wrappers_gateway.py
  - cmd_haiku45_info, cmd_haiku45_call
              → interfaces/cli/commands/wrapper_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.model_wrappers import (
    HAIKU45_ALIAS,
    HAIKU45_INFO,
    HAIKU45_MODEL_ID,
    MESSAGES_ENDPOINT,
    MIN_THINKING_BUDGET,
    build_thinking_param,
    resolve_model_id,
    validate_fast_mode,
)
from domain.model_wrappers import (
    estimate_haiku45_cost_usd as estimate_cost_usd,
)
from domain.model_wrappers import (
    validate_haiku45_inference_geo as validate_inference_geo,
)
from infrastructure.anthropic_api.model_wrappers_gateway import Haiku45Client
from interfaces.cli.commands.wrapper_commands import cmd_haiku45_call, cmd_haiku45_info

__all__ = [
    "MESSAGES_ENDPOINT",
    "HAIKU45_MODEL_ID",
    "HAIKU45_ALIAS",
    "MIN_THINKING_BUDGET",
    "HAIKU45_INFO",
    "resolve_model_id",
    "build_thinking_param",
    "validate_fast_mode",
    "validate_inference_geo",
    "Haiku45Client",
    "estimate_cost_usd",
    "cmd_haiku45_info",
    "cmd_haiku45_call",
]

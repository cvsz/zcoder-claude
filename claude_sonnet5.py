"""
claude_sonnet5.py — Claude Sonnet 5 support (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Real implementation moved 2026-08-21:
  - MESSAGES_ENDPOINT, SONNET5_MODEL_ID, PROMO_PRICE_IN_USD,
    PROMO_PRICE_OUT_USD, STANDARD_PRICE_IN_USD, STANDARD_PRICE_OUT_USD,
    PROMO_END_DATE, SONNET5_INFO, current_pricing, estimate_cost_usd
    (now estimate_sonnet5_cost_usd), validate_service_tier,
    validate_sampling_params
    → domain/model_wrappers.py
  - Sonnet5Client → infrastructure/anthropic_api/model_wrappers_gateway.py
  - cmd_sonnet5_info, cmd_sonnet5_call, cmd_sonnet5_cost
              → interfaces/cli/commands/wrapper_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.model_wrappers import (
    MESSAGES_ENDPOINT,
    PROMO_END_DATE,
    PROMO_PRICE_IN_USD,
    PROMO_PRICE_OUT_USD,
    SONNET5_INFO,
    SONNET5_MODEL_ID,
    STANDARD_PRICE_IN_USD,
    STANDARD_PRICE_OUT_USD,
    current_pricing,
    validate_sampling_params,
    validate_service_tier,
)
from domain.model_wrappers import (
    estimate_sonnet5_cost_usd as estimate_cost_usd,
)
from infrastructure.anthropic_api.model_wrappers_gateway import Sonnet5Client
from interfaces.cli.commands.wrapper_commands import (
    cmd_sonnet5_call,
    cmd_sonnet5_cost,
    cmd_sonnet5_info,
)

__all__ = [
    "MESSAGES_ENDPOINT",
    "SONNET5_MODEL_ID",
    "PROMO_PRICE_IN_USD",
    "PROMO_PRICE_OUT_USD",
    "STANDARD_PRICE_IN_USD",
    "STANDARD_PRICE_OUT_USD",
    "PROMO_END_DATE",
    "SONNET5_INFO",
    "current_pricing",
    "estimate_cost_usd",
    "validate_service_tier",
    "validate_sampling_params",
    "Sonnet5Client",
    "cmd_sonnet5_info",
    "cmd_sonnet5_call",
    "cmd_sonnet5_cost",
]

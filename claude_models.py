"""
claude_models.py — COMPATIBILITY SHIM (Clean Architecture refactor, 2026-08-14)

This file's real content moved to three places:
  • Pure model data/lifecycle logic  -> domain/models/catalog.py
  • Live Anthropic API calls         -> infrastructure/anthropic_api/models_gateway.py
  • CLI presentation (cmd_* / print) -> interfaces/cli/commands/model_commands.py

This shim re-exports every public name that used to live here so existing
`from claude_models import X` call sites (main.py, tests/) keep working
without modification during the migration (Strangler Fig pattern). New code
should import from the three locations above directly, not from here.
Once every call site has been updated, this file can be deleted.
"""

from domain.models.catalog import (
    MODEL_CATALOG,
    FAST_MODE_SUPPORTED, FAST_MODE_REMOVED_ERROR, FAST_MODE_REMOVED_SILENT,
    validate_fast_mode,
    SERVICE_TIER_UNSUPPORTED,
    INFERENCE_GEO_SUPPORTED, INFERENCE_GEO_PRICING_MULTIPLIER, INFERENCE_GEO_MULTIPLIER,
    RETIRED_MODELS, check_retired,
    DEPRECATED_MODELS, check_deprecated,
    UPGRADE_TARGETS, MODEL_ID_ALIASES, _upgrade_source_ids,
    PRICE, DEFAULT_PRICE, get_price,
    LONG_CONTEXT_SURCHARGE, estimate_cost_usd,
)
from infrastructure.anthropic_api.models_gateway import (
    ModelsAPI, ComputerUseCoder, AdaptiveThinkingCoder,
    MODELS_ENDPOINT, MESSAGES_ENDPOINT,
)
from interfaces.cli.commands.model_commands import (
    cmd_list_models, cmd_model_info, cmd_check_deprecated,
    cmd_upgrade_all,
    cmd_computer_use, cmd_adaptive_thinking,
)
from application.models_service import _walk_upgrade_candidates

__all__ = [
    "MODEL_CATALOG", "FAST_MODE_SUPPORTED", "FAST_MODE_REMOVED_ERROR",
    "FAST_MODE_REMOVED_SILENT", "validate_fast_mode", "SERVICE_TIER_UNSUPPORTED",
    "INFERENCE_GEO_SUPPORTED", "INFERENCE_GEO_PRICING_MULTIPLIER", "INFERENCE_GEO_MULTIPLIER",
    "RETIRED_MODELS", "check_retired", "DEPRECATED_MODELS", "check_deprecated",
    "UPGRADE_TARGETS", "MODEL_ID_ALIASES", "_upgrade_source_ids",
    "PRICE", "DEFAULT_PRICE", "get_price", "LONG_CONTEXT_SURCHARGE", "estimate_cost_usd",
    "ModelsAPI", "ComputerUseCoder", "AdaptiveThinkingCoder", "MODELS_ENDPOINT", "MESSAGES_ENDPOINT",
    "cmd_list_models", "cmd_model_info", "cmd_check_deprecated",
    "_walk_upgrade_candidates", "cmd_upgrade_all", "cmd_computer_use", "cmd_adaptive_thinking",
]

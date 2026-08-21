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

from application.models_service import _walk_upgrade_candidates
from domain.models.catalog import (
    DEFAULT_PRICE,
    DEPRECATED_MODELS,
    FAST_MODE_REMOVED_ERROR,
    FAST_MODE_REMOVED_SILENT,
    FAST_MODE_SUPPORTED,
    INFERENCE_GEO_MULTIPLIER,
    INFERENCE_GEO_PRICING_MULTIPLIER,
    INFERENCE_GEO_SUPPORTED,
    LONG_CONTEXT_SURCHARGE,
    MODEL_CATALOG,
    MODEL_ID_ALIASES,
    PRICE,
    RETIRED_MODELS,
    SERVICE_TIER_UNSUPPORTED,
    UPGRADE_TARGETS,
    _upgrade_source_ids,
    check_deprecated,
    check_retired,
    estimate_cost_usd,
    get_price,
    validate_fast_mode,
)
from infrastructure.anthropic_api.models_gateway import (
    MESSAGES_ENDPOINT,
    MODELS_ENDPOINT,
    AdaptiveThinkingCoder,
    ComputerUseCoder,
    ModelsAPI,
)
from interfaces.cli.commands.model_commands import (
    cmd_adaptive_thinking,
    cmd_check_deprecated,
    cmd_computer_use,
    cmd_list_models,
    cmd_model_info,
    cmd_upgrade_all,
)

__all__ = [
    "MODEL_CATALOG",
    "FAST_MODE_SUPPORTED",
    "FAST_MODE_REMOVED_ERROR",
    "FAST_MODE_REMOVED_SILENT",
    "validate_fast_mode",
    "SERVICE_TIER_UNSUPPORTED",
    "INFERENCE_GEO_SUPPORTED",
    "INFERENCE_GEO_PRICING_MULTIPLIER",
    "INFERENCE_GEO_MULTIPLIER",
    "RETIRED_MODELS",
    "check_retired",
    "DEPRECATED_MODELS",
    "check_deprecated",
    "UPGRADE_TARGETS",
    "MODEL_ID_ALIASES",
    "_upgrade_source_ids",
    "PRICE",
    "DEFAULT_PRICE",
    "get_price",
    "LONG_CONTEXT_SURCHARGE",
    "estimate_cost_usd",
    "ModelsAPI",
    "ComputerUseCoder",
    "AdaptiveThinkingCoder",
    "MODELS_ENDPOINT",
    "MESSAGES_ENDPOINT",
    "cmd_list_models",
    "cmd_model_info",
    "cmd_check_deprecated",
    "_walk_upgrade_candidates",
    "cmd_upgrade_all",
    "cmd_computer_use",
    "cmd_adaptive_thinking",
]

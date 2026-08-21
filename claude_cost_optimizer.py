"""
claude_cost_optimizer.py — Cost-aware model routing (compatibility shim)
AI Model Coder CLI v1.53.1 (Clean Architecture refactor, Phase D, Context #7)

This module used to contain the full implementation (182 lines: local
pricing re-exports, classify_complexity/select_model, the OptimizedResponse
dataclass, optimized_call's real HTTP call + spend logging, and 3 cmd_*
CLI entry points). It has been split into:

  domain/observability.py                         — pure routing logic
                                                      (classify_complexity,
                                                      select_model,
                                                      OptimizedResponse,
                                                      estimate_cost —
                                                      delegates to
                                                      domain/models/catalog.py's
                                                      estimate_cost_usd()
                                                      instead of
                                                      re-implementing the
                                                      surcharge/geo logic,
                                                      see that module's
                                                      docstring for the
                                                      dedup finding)
  infrastructure/local_storage/observability_store.py — SPEND_LOG read/
                                                      write/clear
  infrastructure/anthropic_api/observability_gateway.py — optimized_call's
                                                      real anthropic SDK call
  application/observability_service.py             — use-case layer
  interfaces/cli/commands/observability_commands.py — print(), the 3
                                                      cmd_* entry points

This file re-exports every name the old module used to export, so
existing imports (`from claude_cost_optimizer import cmd_optimized`, etc.,
used by main.py) keep working unmodified. See exec-planning.md §5
(migration playbook).
"""

from application.observability_service import optimized_call
from domain.models.catalog import INFERENCE_GEO_MULTIPLIER, INFERENCE_GEO_SUPPORTED, LONG_CONTEXT_SURCHARGE
from domain.observability import (
    DEFAULT_PRICE,
    PRICE,
    SONNET5_INTRO_PRICE,
    TIER_MODELS,
    OptimizedResponse,
    classify_complexity,
    estimate_cost,
    select_model,
)
from infrastructure.local_storage.observability_store import (
    SPEND_LOG,
)
from infrastructure.local_storage.observability_store import (
    log_spend as _log_spend,
)
from interfaces.cli.commands.observability_commands import (
    cmd_cost_reset,
    cmd_cost_summary,
    cmd_optimized,
)

__all__ = [
    "PRICE",
    "DEFAULT_PRICE",
    "LONG_CONTEXT_SURCHARGE",
    "INFERENCE_GEO_MULTIPLIER",
    "INFERENCE_GEO_SUPPORTED",
    "SPEND_LOG",
    "SONNET5_INTRO_PRICE",
    "TIER_MODELS",
    "estimate_cost",
    "classify_complexity",
    "select_model",
    "OptimizedResponse",
    "optimized_call",
    "_log_spend",
    "cmd_optimized",
    "cmd_cost_summary",
    "cmd_cost_reset",
]

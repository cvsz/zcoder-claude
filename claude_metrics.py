"""
claude_metrics.py — Observability & Usage Metrics (compatibility shim)
AI Model Coder CLI v1.53.1 (Clean Architecture refactor, Phase D, Context #7)

This module used to contain the full implementation (152 lines: LOG_PATH,
the PRICE_TABLE re-export, _price(), record(), load_log(), summarise(),
and 3 cmd_* CLI entry points). It has been split into:

  domain/observability.py                             — summarise_metrics()
                                                          (was summarise()),
                                                          price_lookup()
                                                          (was _price()) —
                                                          now delegates to
                                                          domain/models/
                                                          catalog.py's
                                                          estimate_cost_usd()
                                                          instead of a bare
                                                          PRICE_TABLE lookup
  infrastructure/local_storage/observability_store.py — METRICS_LOG_PATH
                                                          (was LOG_PATH),
                                                          record_metric()
                                                          (was record()),
                                                          load_metrics_log()
                                                          (was load_log()),
                                                          clear_metrics_log(),
                                                          write_metrics_export()
  application/observability_service.py                — use-case layer
  interfaces/cli/commands/observability_commands.py    — print(), the 3
                                                          cmd_* entry points

PRICE_TABLE is rebuilt here (rather than re-exported directly) since the
original shape — {model_id: (in_price, out_price)} tuples — was specific
to this module; domain/observability.py works from catalog.py's PRICE
dict shape ({"in":.., "out":..}) directly and has no reason to keep the
tuple form itself.

This file re-exports every name the old module used to export under its
original name, so existing imports (`from claude_metrics import record`,
etc., used by main.py and tests/test_claude_metrics.py) keep working
unmodified — including LOG_PATH, though see tests/test_claude_metrics.py's
2026-08-19 fixture note: patching this shim's LOG_PATH no longer reaches
record()/load_log()'s actual I/O, which now resolves METRICS_LOG_PATH from
infrastructure/local_storage/observability_store.py's own module
namespace — the exact "second repoint" pattern exec-planning.md §5 step 5
describes; the test fixture was updated to patch the store module
directly instead. See exec-planning.md §5 (migration playbook).
"""

from domain.models.catalog import DEFAULT_PRICE as _CATALOG_DEFAULT
from domain.models.catalog import PRICE as _CATALOG_PRICE
from domain.observability import price_lookup as _price
from domain.observability import summarise_metrics as summarise
from infrastructure.local_storage.observability_store import (
    METRICS_LOG_PATH as LOG_PATH,
)
from infrastructure.local_storage.observability_store import (
    clear_metrics_log,
    write_metrics_export,
)
from infrastructure.local_storage.observability_store import (
    load_metrics_log as load_log,
)
from infrastructure.local_storage.observability_store import (
    record_metric as record,
)
from interfaces.cli.commands.observability_commands import (
    cmd_metrics_clear,
    cmd_metrics_export,
    cmd_metrics_show,
)

PRICE_TABLE = {model_id: (p["in"], p["out"]) for model_id, p in _CATALOG_PRICE.items()}
DEFAULT_PRICE = (_CATALOG_DEFAULT["in"], _CATALOG_DEFAULT["out"])

__all__ = [
    "LOG_PATH",
    "PRICE_TABLE",
    "DEFAULT_PRICE",
    "_price",
    "record",
    "load_log",
    "summarise",
    "clear_metrics_log",
    "write_metrics_export",
    "cmd_metrics_show",
    "cmd_metrics_clear",
    "cmd_metrics_export",
]

"""
application/observability_service.py — use-case layer for the Cost,
Metrics, Observability & Eval bounded context
AI Model Coder CLI v1.53.1 (Clean Architecture refactor, Phase D, Context #7)

Orchestrates domain/observability.py + infrastructure/local_storage/
observability_store.py + infrastructure/anthropic_api/observability_gateway.py
— no print() of its own. Extracted 2026-08-19 from claude_cost_optimizer.py,
claude_metrics.py, claude_observability.py, and claude_eval.py's cmd_*
bodies, completing the split that domain/observability.py and the two
infra layers started earlier in this session.

Two deliberate fidelity notes carried over from the store/gateway layers
(not re-litigated here, see those modules' docstrings for the reasoning):
  - eval_run()'s optional `output` write only ever captures the *first*
    result, matching claude_eval.py's original (slightly odd) behavior.
  - eval_list() returns None (not []) when EVALS_DIR doesn't exist at all,
    so cmd_eval_list can reproduce the original's exact "message vs.
    silent" split between "no directory yet" and "directory exists but
    empty".
"""

from typing import Callable, List, Optional

from domain.observability import (
    EvalCase, EvalRun, OptimizedResponse,
    classify_complexity, select_model, summarise_metrics,
    build_latency_report,
)
from infrastructure.anthropic_api.observability_gateway import (
    optimized_call as _gateway_optimized_call,
    EvalRunner, analyze_errors,
)
from infrastructure.local_storage.observability_store import (
    EVALS_DIR,
    read_spend_log, clear_spend_log,
    load_metrics_log, clear_metrics_log, write_metrics_export,
    read_observability_logs, clear_observability_log,
    save_eval_run, load_eval_run_summaries, load_eval_suite,
    write_eval_suite_scaffold, write_eval_first_result_json,
)

_NOOP = lambda *a, **k: None  # noqa: E731


# ── Cost Optimizer (claude_cost_optimizer.py) ────────────────────────────

def optimized_call(prompt: str, api_key: str, force_model: Optional[str] = None,
                   max_tokens: int = 2048, service_tier: Optional[str] = None,
                   inference_geo: Optional[str] = None) -> OptimizedResponse:
    complexity = classify_complexity(prompt)
    model = select_model(complexity, force_model)
    return _gateway_optimized_call(prompt, api_key, model, complexity,
                                   max_tokens=max_tokens, service_tier=service_tier,
                                   inference_geo=inference_geo)


def cost_summary(limit: int = 20) -> Optional[dict]:
    """Returns None when there's no spend log yet (matches the original's
    SPEND_LOG.exists() check), else {"total", "count", "recent"}."""
    entries = read_spend_log()
    if not entries:
        return None
    return {"total": sum(e["cost_usd"] for e in entries),
            "count": len(entries), "recent": entries[-limit:]}


def cost_reset() -> bool:
    """Returns True if a log file existed and was cleared."""
    return clear_spend_log()


# ── Metrics (claude_metrics.py) ──────────────────────────────────────────

def metrics_summary(today_only: bool = False, model_filter: Optional[str] = None) -> dict:
    entries = load_metrics_log(today_only=today_only, model_filter=model_filter)
    return summarise_metrics(entries)


def metrics_clear() -> None:
    clear_metrics_log()


def metrics_export(output_path: str, today_only: bool = False) -> int:
    """Returns the number of entries exported."""
    entries = load_metrics_log(today_only=today_only)
    summary = summarise_metrics(entries)
    write_metrics_export(output_path, entries, summary)
    return len(entries)


# ── Observability (claude_observability.py) ──────────────────────────────

def obs_latency_report(hours: int = 24) -> Optional[dict]:
    records = read_observability_logs(hours)
    return build_latency_report(records, hours)


def obs_errors(api_key: str, model: str, hours: int = 24) -> Optional[str]:
    """Returns None when there are no errors in the window (matches the
    original's "No errors in logs." branch), else the analysis text."""
    records = read_observability_logs(hours)
    errors = [r for r in records if r.get("error")]
    if not errors:
        return None
    return analyze_errors(api_key, model, errors)


def obs_clear() -> bool:
    return clear_observability_log()


def obs_tail(n: int = 20) -> List[dict]:
    return read_observability_logs(hours=999999)[-n:]


# ── Eval harness (claude_eval.py) ─────────────────────────────────────────

def load_suite(suite_path: str) -> List[EvalCase]:
    return load_eval_suite(suite_path)


def eval_run(cases: List[EvalCase], api_key: str, model: str,
            judge_model: str = "claude-sonnet-5", threshold: float = 0.7,
            on_case: Callable[[str, float, bool, int], None] = _NOOP) -> EvalRun:
    runner = EvalRunner(api_key, model, judge_model, threshold)
    return runner.run(cases, on_case=on_case)


def persist_eval_run(run: EvalRun) -> str:
    return save_eval_run(run)


def write_eval_output(output_path: str, run: EvalRun) -> None:
    write_eval_first_result_json(output_path, run)


def eval_list(limit: int = 20) -> Optional[List[dict]]:
    if not EVALS_DIR.exists():
        return None
    return load_eval_run_summaries(limit)


def eval_scaffold(output_path: str) -> None:
    write_eval_suite_scaffold(output_path)

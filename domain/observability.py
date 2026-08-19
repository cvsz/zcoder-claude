"""
domain/observability.py — Cost, Metrics, Observability & Eval domain layer
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase D, Context #7)

Pure data + pure functions for the bounded context covering
claude_cost_optimizer.py, claude_metrics.py, claude_observability.py, and
claude_eval.py. No I/O, no print(), no `import anthropic` here.

Cost dedup finding (2026-08-19): claude_cost_optimizer.py's estimate_cost()
and claude_metrics.py's _price() each re-implemented the exact
surcharge/inference_geo pricing logic that domain/models/catalog.py's
estimate_cost_usd() already canonicalizes (per that function's own
docstring: "Every claude_*.py cost-estimation helper should delegate to
this instead of re-implementing the surcharge/multiplier logic" — added
during an earlier session but not yet followed here since these 2 files
weren't migrated yet). Both now delegate to it — see estimate_cost() and
price_lookup() below. This is the same class of bug (Sonnet 5 pricing
duplicated and going stale in multiple files) the whole refactor exists
to fix (see catalog.py's own docstring and §0 of exec-planning.md).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from domain.models.catalog import PRICE, DEFAULT_PRICE, estimate_cost_usd

# ── Cost routing (claude_cost_optimizer.py) ─────────────────────────────

# SONNET5_INTRO_PRICE is kept only as an alias for backward compatibility
# with existing callers that pass use_intro_pricing=True — it now resolves
# to the same figure as PRICE["claude-sonnet-5"] since there's no longer a
# separate promo rate (see domain/models/catalog.py).
SONNET5_INTRO_PRICE = PRICE["claude-sonnet-5"]
TIER_MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-5", "claude-opus-4-8"]


def estimate_cost(model: str, in_tok: int, out_tok: int,
                  use_intro_pricing: bool = False,
                  inference_geo: str = "global") -> float:
    """Back-compat wrapper around catalog.estimate_cost_usd(). Kept as its
    own name/signature (rather than callers switching to estimate_cost_usd
    directly) since `use_intro_pricing` is still part of this bounded
    context's public API — it's a no-op now that SONNET5_INTRO_PRICE
    always equals the base price, so it doesn't need to be threaded
    through to the catalog function at all."""
    return estimate_cost_usd(model, in_tok, out_tok, inference_geo=inference_geo)


def classify_complexity(prompt: str) -> str:
    """Simple heuristic: short simple -> haiku; long/complex -> sonnet; very long or code-heavy -> opus."""
    words = len(prompt.split())
    code_markers = sum(prompt.count(k) for k in ["def ", "class ", "function ", "SELECT ", "CREATE "])
    if words > 800 or code_markers > 5: return "high"
    if words > 200 or code_markers > 1: return "medium"
    return "low"


def select_model(complexity: str, force: Optional[str] = None) -> str:
    if force: return force
    return {"low": TIER_MODELS[0], "medium": TIER_MODELS[1], "high": TIER_MODELS[2]}[complexity]


@dataclass
class OptimizedResponse:
    text:       str
    model_used: str
    complexity: str
    in_tokens:  int
    out_tokens: int
    cost_usd:   float
    latency_ms: int


# ── Metrics (claude_metrics.py) ──────────────────────────────────────────

def price_lookup(model: str, input_tok: int, output_tok: int) -> float:
    """claude_metrics.py's former _price() — now delegates to the catalog
    canonical estimator instead of a bare PRICE_TABLE lookup (see module
    docstring). Global/no-surcharge inputs (metrics.py never threaded
    inference_geo or long-context awareness) give identical results to
    the original bare lookup for every case the pre-existing test suite
    covers."""
    return estimate_cost_usd(model, input_tok, output_tok)


def summarise_metrics(entries: List[dict]) -> dict:
    if not entries:
        return {"calls": 0}
    by_model: Dict[str, dict] = {}
    for e in entries:
        m = e.get("model", "unknown")
        if m not in by_model:
            by_model[m] = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                           "cost_usd": 0.0, "latency_seconds": 0.0}
        s = by_model[m]
        s["calls"] += 1
        s["input_tokens"] += e.get("input_tokens", 0)
        s["output_tokens"] += e.get("output_tokens", 0)
        s["cost_usd"] += e.get("cost_usd", 0.0)
        s["latency_seconds"] += e.get("latency_seconds", 0.0)
    for m in by_model:
        s = by_model[m]
        s["avg_latency_seconds"] = round(s["latency_seconds"] / s["calls"], 3)
        s["cost_usd"] = round(s["cost_usd"], 6)

    return {
        "calls": len(entries),
        "total_cost_usd": round(sum(e.get("cost_usd", 0) for e in entries), 6),
        "total_input_tokens": sum(e.get("input_tokens", 0) for e in entries),
        "total_output_tokens": sum(e.get("output_tokens", 0) for e in entries),
        "by_model": by_model,
    }


# ── Observability (claude_observability.py) ─────────────────────────────

def histogram(values: List[float], buckets: int = 6) -> str:
    if not values: return "(no data)"
    lo, hi = min(values), max(values)
    if hi == lo: return f"all values = {lo:.0f}"
    width = (hi - lo) / buckets
    counts = [0] * buckets
    for v in values:
        idx = min(int((v - lo) / width), buckets - 1)
        counts[idx] += 1
    lines = []
    for i, c in enumerate(counts):
        label = f"{lo + i*width:.0f}\u2013{lo + (i+1)*width:.0f}"
        bar   = "\u2588" * max(1, int(c / max(counts) * 20)) if c else ""
        lines.append(f"  {label:>12}ms  {bar} {c}")
    return "\n".join(lines)


def build_latency_report(records: List[dict], hours: int) -> Optional[dict]:
    """Pure aggregation extracted from claude_observability.py's
    latency_report(), which used to compute *and* print() in the same
    function. Returns None (caller prints "no data") when there are no
    records in the window; otherwise a dict with everything the CLI layer
    needs to print, including the pre-rendered histogram text."""
    if not records:
        return None
    lats = [r["latency_ms"] for r in records if "latency_ms" in r]
    by_model: Dict[str, List[float]] = {}
    for r in records:
        by_model.setdefault(r.get("model", "?"), []).append(r.get("latency_ms", 0))
    errors = [r for r in records if r.get("error")]
    sorted_lats = sorted(lats)
    return {
        "hours": hours,
        "count": len(records),
        "error_count": len(errors),
        "p50_ms": sorted_lats[len(sorted_lats) // 2],
        "p95_ms": sorted_lats[int(len(sorted_lats) * 0.95)],
        "avg_ms": sum(lats) / len(lats),
        "histogram_text": histogram(lats),
        "by_model": {m: {"calls": len(ls), "avg_ms": sum(ls) / len(ls)}
                    for m, ls in sorted(by_model.items())},
    }


def build_request_record(model: str, prompt: str, response: str,
                         latency_ms: int, in_tokens: int, out_tokens: int,
                         error: Optional[str] = None,
                         tags: Optional[List[str]] = None) -> dict:
    """Pure record-shaping extracted from claude_observability.py's
    record_request() — building the dict is pure; only the append-to-file
    half (now infrastructure/local_storage/observability_store.py's
    log_observability_request()) is I/O."""
    return {"req_id": str(uuid.uuid4())[:8], "ts": datetime.now().isoformat(),
            "model": model, "prompt_preview": prompt[:120],
            "response_preview": response[:120] if response else "",
            "latency_ms": latency_ms, "in_tokens": in_tokens,
            "out_tokens": out_tokens, "error": error, "tags": tags or []}


# ── Eval harness (claude_eval.py) ────────────────────────────────────────

@dataclass
class EvalCase:
    case_id:  str
    prompt:   str
    expected: str
    tags:     List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    case_id:    str
    prompt:     str
    expected:   str
    actual:     str
    score:      float       # 0.0-1.0
    passed:     bool
    latency_ms: int
    model:      str
    reason:     str = ""


@dataclass
class EvalRun:
    run_id:  str
    model:   str
    cases:   int
    passed:  int
    avg_score: float
    avg_latency_ms: float
    results: List[EvalResult]
    ts:      str = field(default_factory=lambda: datetime.now().isoformat())

    def summary(self) -> str:
        return (f"Run {self.run_id}  model={self.model}  "
                f"{self.passed}/{self.cases} passed  "
                f"avg_score={self.avg_score:.2f}  "
                f"avg_latency={self.avg_latency_ms:.0f}ms")


def build_eval_run(run_id: str, model: str, results: List[EvalResult]) -> EvalRun:
    """Pure aggregation extracted from claude_eval.py's EvalRunner.run(),
    which used to build this same summary inline alongside its print()
    calls and the actual model/judge HTTP calls."""
    passed  = sum(1 for r in results if r.passed)
    avg_score = sum(r.score for r in results) / len(results) if results else 0
    avg_lat   = sum(r.latency_ms for r in results) / len(results) if results else 0
    return EvalRun(run_id=run_id, model=model, cases=len(results),
                   passed=passed, avg_score=avg_score, avg_latency_ms=avg_lat,
                   results=results)


__all__ = [
    "SONNET5_INTRO_PRICE", "TIER_MODELS", "estimate_cost", "classify_complexity",
    "select_model", "OptimizedResponse", "price_lookup", "summarise_metrics",
    "histogram", "build_latency_report", "build_request_record",
    "EvalCase", "EvalResult", "EvalRun", "build_eval_run",
    "PRICE", "DEFAULT_PRICE",
]

"""
infrastructure/local_storage/observability_store.py — disk I/O for the
Cost, Metrics, Observability & Eval bounded context.
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase D, Context #7)

Every function here does file I/O and nothing else — no print(), no
`import anthropic`, no complexity/scoring/aggregation logic (that's
domain/observability.py's job). Extracted 2026-08-19 from
claude_cost_optimizer.py (_log_spend, SPEND_LOG), claude_metrics.py
(record, load_log, LOG_PATH), claude_observability.py (_log, _read_logs,
OBS_DIR/LOG_FILE), and claude_eval.py (_save_run, EVALS_DIR, and the
suite-file read/write halves of cmd_eval_run/cmd_eval_scaffold).
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from domain.observability import EvalCase, EvalRun, price_lookup

# ── Cost log (claude_cost_optimizer.py) ──────────────────────────────────

SPEND_LOG = Path.home() / ".ai-coder" / "cost_log.json"


def log_spend(model: str, in_tok: int, out_tok: int, cost: float, prompt_preview: str) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if SPEND_LOG.exists():
        try: entries = json.loads(SPEND_LOG.read_text())
        except Exception: pass
    entries.append({"ts": datetime.now().isoformat(), "model": model,
                   "in_tok": in_tok, "out_tok": out_tok, "cost_usd": round(cost, 6),
                   "prompt": prompt_preview[:80]})
    SPEND_LOG.write_text(json.dumps(entries[-5000:], indent=2))


def read_spend_log() -> List[dict]:
    if not SPEND_LOG.exists():
        return []
    return json.loads(SPEND_LOG.read_text())


def clear_spend_log() -> bool:
    """Returns True if a log file existed and was removed."""
    if SPEND_LOG.exists():
        SPEND_LOG.unlink()
        return True
    return False


# ── Metrics log (claude_metrics.py) ──────────────────────────────────────

METRICS_LOG_PATH = Path.home() / ".ai-coder" / "metrics.jsonl"


def record_metric(model: str, input_tokens: int, output_tokens: int,
                  latency_seconds: float, command: str = "", stop_reason: str = "") -> None:
    """v1.11.0: a request that returns stop_reason:"refusal" with no
    generated output is documented as not billed on the Claude API — see
    domain/observability.py's price_lookup() delegation for the pricing
    half of this, and claude_fable5.py's call_with_fallback() for where
    stop_reason gets threaded through from the actual API response."""
    METRICS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    not_billed = stop_reason == "refusal" and output_tokens == 0
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": 0.0 if not_billed else round(price_lookup(model, input_tokens, output_tokens), 6),
        "latency_seconds": round(latency_seconds, 3),
        "command": command,
        "stop_reason": stop_reason,
        "not_billed": not_billed,
    }
    with open(METRICS_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_metrics_log(today_only: bool = False, model_filter: Optional[str] = None) -> List[dict]:
    if not METRICS_LOG_PATH.exists():
        return []
    today_str = date.today().isoformat()
    entries = []
    with open(METRICS_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if today_only and not e.get("ts", "").startswith(today_str):
                continue
            if model_filter and e.get("model") != model_filter:
                continue
            entries.append(e)
    return entries


def clear_metrics_log() -> None:
    if METRICS_LOG_PATH.exists():
        METRICS_LOG_PATH.unlink()


# ── Observability request log (claude_observability.py) ─────────────────

OBS_DIR  = Path.home() / ".ai-coder" / "observability"
OBS_LOG_FILE = OBS_DIR / "requests.jsonl"


def log_observability_request(record: dict) -> None:
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OBS_LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_observability_logs(hours: int = 24) -> List[dict]:
    if not OBS_LOG_FILE.exists(): return []
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    records = []
    with open(OBS_LOG_FILE) as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("ts", "") >= cutoff: records.append(r)
            except Exception: pass
    return records


def clear_observability_log() -> bool:
    if OBS_LOG_FILE.exists():
        OBS_LOG_FILE.unlink()
        return True
    return False


# ── Eval suites & runs (claude_eval.py) ──────────────────────────────────

EVALS_DIR = Path.home() / ".ai-coder" / "evals"


def save_eval_run(run: EvalRun) -> str:
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    p = EVALS_DIR / f"{run.run_id}.json"
    p.write_text(json.dumps({
        "run_id": run.run_id, "model": run.model, "ts": run.ts,
        "cases": run.cases, "passed": run.passed,
        "avg_score": run.avg_score, "avg_latency_ms": run.avg_latency_ms,
        "results": [{
            "case_id": r.case_id, "score": r.score, "passed": r.passed,
            "latency_ms": r.latency_ms, "reason": r.reason,
            "actual": r.actual[:500]
        } for r in run.results]
    }, indent=2))
    return str(p)


def load_eval_run_summaries(limit: int = 20) -> List[dict]:
    """Parsed contents of the most recent `limit` saved eval-run JSON
    files, newest first. Silently skips any file that fails to parse
    (matches claude_eval.py's original cmd_eval_list behavior)."""
    if not EVALS_DIR.exists():
        return []
    summaries = []
    for p in sorted(EVALS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            summaries.append(json.loads(p.read_text()))
        except Exception:
            pass
    return summaries


def load_eval_suite(path: str) -> List[EvalCase]:
    data = json.loads(Path(path).read_text())
    return [EvalCase(**c) for c in data]


def write_eval_suite_scaffold(output_path: str) -> None:
    suite = [
        {"case_id": "greet_01", "prompt": "Say hello in one sentence.",
         "expected": "Response is a friendly single-sentence greeting."},
        {"case_id": "code_01",  "prompt": "Write a Python function to reverse a string.",
         "expected": "Response contains a working Python function that reverses a string."},
    ]
    Path(output_path).write_text(json.dumps(suite, indent=2))


__all__ = [
    "SPEND_LOG", "log_spend", "read_spend_log", "clear_spend_log",
    "METRICS_LOG_PATH", "record_metric", "load_metrics_log", "clear_metrics_log",
    "OBS_DIR", "OBS_LOG_FILE", "log_observability_request", "read_observability_logs",
    "clear_observability_log",
    "EVALS_DIR", "save_eval_run", "load_eval_run_summaries", "load_eval_suite",
    "write_eval_suite_scaffold",
]

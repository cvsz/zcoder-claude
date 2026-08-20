"""
interfaces/cli/commands/observability_commands.py — CLI presentation for
the Cost, Metrics, Observability & Eval bounded context
AI Model Coder CLI v1.53.1 (Clean Architecture refactor, Phase D, Context #7)

Only print() lives here — all real work delegated to
application/observability_service.py. Extracted 2026-08-19 from
claude_cost_optimizer.py's cmd_optimized/cmd_cost_summary/cmd_cost_reset,
claude_metrics.py's cmd_metrics_show/cmd_metrics_clear/cmd_metrics_export,
claude_observability.py's cmd_obs_latency/cmd_obs_errors/cmd_obs_clear/
cmd_obs_tail, and claude_eval.py's cmd_eval_run/cmd_eval_compare/
cmd_eval_list/cmd_eval_scaffold.
"""

from typing import Optional

from application import observability_service as service

__all__ = [
    "cmd_optimized", "cmd_cost_summary", "cmd_cost_reset",
    "cmd_metrics_show", "cmd_metrics_clear", "cmd_metrics_export",
    "cmd_obs_latency", "cmd_obs_errors", "cmd_obs_clear", "cmd_obs_tail",
    "cmd_eval_run", "cmd_eval_compare", "cmd_eval_list", "cmd_eval_scaffold",
]


def _on_case(case_id: str, score: float, passed: bool, latency_ms: int):
    print(f"  {'✓' if passed else '✗'} {case_id} score={score:.2f} ({latency_ms}ms)")


# ── Cost Optimizer ────────────────────────────────────────────────────────

def cmd_optimized(prompt: str, api_key: str, verbose: bool = False,
                  force_model: Optional[str] = None):
    r = service.optimized_call(prompt, api_key, force_model=force_model)
    if verbose:
        print(f"[model={r.model_used}  complexity={r.complexity}  "
              f"cost=${r.cost_usd:.5f}  {r.latency_ms}ms]\n")
    print(r.text)


def cmd_cost_summary(limit: int = 20):
    s = service.cost_summary(limit)
    if s is None:
        print("No cost log found.")
        return
    print(f"Total spend logged: ${s['total']:.4f}  ({s['count']} calls)\n")
    print(f"{'Timestamp':<21} {'Model':<35} {'Cost':>9}  Prompt preview")
    print("─" * 90)
    for e in reversed(s["recent"]):
        print(f"{e['ts'][:19]:<21} {e['model']:<35} ${e['cost_usd']:>8.5f}  {e['prompt']}")


def cmd_cost_reset():
    if service.cost_reset():
        print("✓ Cost log cleared.")
    else:
        print("No log to clear.")


# ── Metrics ──────────────────────────────────────────────────────────────

def cmd_metrics_show(today_only: bool = False, model_filter: Optional[str] = None):
    s = service.metrics_summary(today_only=today_only, model_filter=model_filter)
    if not s.get("calls"):
        print("No metrics recorded yet. API calls are logged automatically after each use.")
        return
    label = "Today's" if today_only else "All-time"
    if model_filter:
        label += f" [{model_filter}]"
    print(f"\n\033[94m{label} Usage\033[0m")
    print(f"  Total calls:    {s['calls']}")
    print(f"  Total cost:     ${s['total_cost_usd']:.4f}")
    print(f"  Input tokens:   {s['total_input_tokens']:,}")
    print(f"  Output tokens:  {s['total_output_tokens']:,}")
    if s.get("by_model"):
        print("\n  \033[1mBy model:\033[0m")
        for model, ms in sorted(s["by_model"].items()):
            print(f"    {model:<40} {ms['calls']} calls  "
                  f"${ms['cost_usd']:.4f}  avg {ms['avg_latency_seconds']}s")
    print()


def cmd_metrics_clear():
    service.metrics_clear()
    print("Metrics log cleared.")


def cmd_metrics_export(output_path: str, today_only: bool = False):
    n = service.metrics_export(output_path, today_only=today_only)
    print(f"Exported {n} entries to {output_path}")


# ── Observability ─────────────────────────────────────────────────────────

def cmd_obs_latency(hours: int = 24):
    report = service.obs_latency_report(hours)
    if report is None:
        print(f"No requests in the last {hours}h.")
        return
    print(f"Requests (last {report['hours']}h): {report['count']}  errors: {report['error_count']}")
    print(f"Latency — p50={report['p50_ms']:.0f}ms  "
          f"p95={report['p95_ms']:.0f}ms  "
          f"avg={report['avg_ms']:.0f}ms\n")
    print("Latency histogram (ms):")
    print(report["histogram_text"])
    print("\nBy model:")
    for m, info in report["by_model"].items():
        print(f"  {m:<40} {info['calls']:>4} calls  avg={info['avg_ms']:.0f}ms")


def cmd_obs_errors(api_key: str, model: str, hours: int = 24):
    text = service.obs_errors(api_key, model, hours)
    if text is None:
        print("No errors in logs.")
        return
    print(text)


def cmd_obs_clear():
    if service.obs_clear():
        print("✓ Observability log cleared.")
    else:
        print("No log to clear.")


def cmd_obs_tail(n: int = 20):
    recs = service.obs_tail(n)
    if not recs:
        print("No records.")
        return
    for r in recs:
        err = f" ERROR: {r['error']}" if r.get("error") else ""
        print(f"{r['ts'][:19]}  {r['model']:<35}  {r.get('latency_ms', 0):>5}ms{err}")


# ── Eval harness ───────────────────────────────────────────────────────────

def cmd_eval_run(suite_path: str, api_key: str, model: str,
                 judge_model: str = "claude-sonnet-5",
                 threshold: float = 0.7, output: Optional[str] = None):
    """Run an eval suite (JSON file of [{case_id, prompt, expected, tags}])"""
    cases = service.load_suite(suite_path)
    print(f"Running {len(cases)} eval cases against {model} …\n")
    run = service.eval_run(cases, api_key, model, judge_model, threshold, on_case=_on_case)
    print(f"\n{run.summary()}")
    path = service.persist_eval_run(run)
    print(f"Results saved → {path}")
    if output:
        service.write_eval_output(output, run)


def cmd_eval_compare(suite_path: str, model_a: str, model_b: str,
                     api_key: str, judge_model: str = "claude-sonnet-5"):
    """Compare two models head-to-head on the same eval suite."""
    cases = service.load_suite(suite_path)
    print(f"Comparing {model_a}  vs  {model_b}  on {len(cases)} cases …\n")
    for m in [model_a, model_b]:
        print(f"── {m} ──")
        run = service.eval_run(cases, api_key, m, judge_model, on_case=_on_case)
        print(f"   {run.summary()}\n")


def cmd_eval_list():
    summaries = service.eval_list()
    if summaries is None:
        print("No eval runs found.")
        return
    for d in summaries:
        try:
            print(f"  [{d['run_id']}] {d['ts'][:16]}  model={d['model']}  "
                  f"{d['passed']}/{d['cases']}  avg={d['avg_score']:.2f}")
        except Exception:
            pass


def cmd_eval_scaffold(output: str):
    """Write a starter eval suite file."""
    service.eval_scaffold(output)
    print(f"✓ Starter eval suite written to {output}")

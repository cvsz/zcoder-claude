"""tests/unit/application/test_observability_service.py

Covers application/observability_service.py — the use-case layer for the
Cost, Metrics, Observability & Eval bounded context, extracted 2026-08-19
(Phase D, Context #7). Per this project's DoD (exec-planning.md §6), every
function here needs direct unit test coverage, not only indirect coverage
via a CLI test capturing stdout.
"""

import application.observability_service as service
from domain.observability import EvalCase, EvalResult, EvalRun, OptimizedResponse

# ── Cost Optimizer ────────────────────────────────────────────────────


def test_optimized_call_selects_model_and_delegates_to_gateway(monkeypatch):
    seen = {}

    def fake_gateway_call(prompt, api_key, model, complexity, **kwargs):
        seen.update(prompt=prompt, api_key=api_key, model=model, complexity=complexity)
        return OptimizedResponse(
            text="ok",
            model_used=model,
            complexity=complexity,
            in_tokens=1,
            out_tokens=1,
            cost_usd=0.0,
            latency_ms=1,
        )

    monkeypatch.setattr(service, "_gateway_optimized_call", fake_gateway_call)
    r = service.optimized_call("hello", "key")
    assert r.text == "ok"
    assert seen["complexity"] == "low"
    assert seen["model"] in ("claude-haiku-4-5-20251001",)


def test_optimized_call_force_model_overrides_routing(monkeypatch):
    seen = {}

    def fake_gateway_call(prompt, api_key, model, complexity, **kwargs):
        seen["model"] = model
        return OptimizedResponse(
            text="ok",
            model_used=model,
            complexity=complexity,
            in_tokens=1,
            out_tokens=1,
            cost_usd=0.0,
            latency_ms=1,
        )

    monkeypatch.setattr(service, "_gateway_optimized_call", fake_gateway_call)
    service.optimized_call("hello", "key", force_model="claude-opus-4-8")
    assert seen["model"] == "claude-opus-4-8"


def test_cost_summary_returns_none_when_no_entries(monkeypatch):
    monkeypatch.setattr(service, "read_spend_log", lambda: [])
    assert service.cost_summary() is None


def test_cost_summary_aggregates_total_and_recent(monkeypatch):
    entries = [
        {"cost_usd": 1.0, "model": "m", "ts": "t", "prompt": "p"},
        {"cost_usd": 2.0, "model": "m", "ts": "t", "prompt": "p"},
    ]
    monkeypatch.setattr(service, "read_spend_log", lambda: entries)
    s = service.cost_summary(limit=1)
    assert s["total"] == 3.0
    assert s["count"] == 2
    assert s["recent"] == entries[-1:]


def test_cost_reset_delegates_to_store(monkeypatch):
    monkeypatch.setattr(service, "clear_spend_log", lambda: True)
    assert service.cost_reset() is True


# ── Metrics ───────────────────────────────────────────────────────────


def test_metrics_summary_delegates_to_store_and_domain(monkeypatch):
    monkeypatch.setattr(
        service,
        "load_metrics_log",
        lambda today_only, model_filter: [
            {"model": "m", "cost_usd": 1.0, "input_tokens": 1, "output_tokens": 1, "latency_seconds": 1.0}
        ],
    )
    s = service.metrics_summary()
    assert s["calls"] == 1


def test_metrics_clear_calls_store(monkeypatch):
    called = []
    monkeypatch.setattr(service, "clear_metrics_log", lambda: called.append(True))
    service.metrics_clear()
    assert called == [True]


def test_metrics_export_writes_and_returns_count(monkeypatch, tmp_path):
    monkeypatch.setattr(
        service, "load_metrics_log", lambda today_only=False, model_filter=None: [{"model": "m"}]
    )
    written = {}
    monkeypatch.setattr(
        service,
        "write_metrics_export",
        lambda path, entries, summary: written.update(path=path, entries=entries),
    )
    n = service.metrics_export(str(tmp_path / "out.json"))
    assert n == 1
    assert written["entries"] == [{"model": "m"}]


# ── Observability ─────────────────────────────────────────────────────


def test_obs_latency_report_empty_returns_none(monkeypatch):
    monkeypatch.setattr(service, "read_observability_logs", lambda hours: [])
    assert service.obs_latency_report() is None


def test_obs_latency_report_delegates_to_domain(monkeypatch):
    monkeypatch.setattr(service, "read_observability_logs", lambda hours: [{"latency_ms": 100, "model": "m"}])
    report = service.obs_latency_report(hours=12)
    assert report["count"] == 1
    assert report["hours"] == 12


def test_obs_errors_none_when_no_errors(monkeypatch):
    monkeypatch.setattr(service, "read_observability_logs", lambda hours: [{"model": "m"}])
    assert service.obs_errors("key", "claude-sonnet-5") is None


def test_obs_errors_calls_gateway_with_filtered_records(monkeypatch):
    records = [{"model": "m", "error": "boom"}, {"model": "m"}]
    monkeypatch.setattr(service, "read_observability_logs", lambda hours: records)
    seen = {}

    def fake_analyze(api_key, model, error_records):
        seen.update(api_key=api_key, model=model, error_records=error_records)
        return "analysis text"

    monkeypatch.setattr(service, "analyze_errors", fake_analyze)
    result = service.obs_errors("key", "claude-sonnet-5")
    assert result == "analysis text"
    assert len(seen["error_records"]) == 1


def test_obs_clear_delegates(monkeypatch):
    monkeypatch.setattr(service, "clear_observability_log", lambda: False)
    assert service.obs_clear() is False


def test_obs_tail_slices_last_n(monkeypatch):
    monkeypatch.setattr(service, "read_observability_logs", lambda hours: [{"i": i} for i in range(30)])
    tail = service.obs_tail(n=5)
    assert len(tail) == 5
    assert tail[-1] == {"i": 29}


# ── Eval harness ──────────────────────────────────────────────────────


def test_load_suite_delegates_to_store(monkeypatch):
    cases = [EvalCase(case_id="c1", prompt="p", expected="e")]
    monkeypatch.setattr(service, "load_eval_suite", lambda path: cases)
    assert service.load_suite("suite.json") == cases


def test_eval_run_delegates_to_gateway_runner(monkeypatch):
    fake_run = EvalRun(
        run_id="r1",
        model="claude-sonnet-5",
        cases=1,
        passed=1,
        avg_score=1.0,
        avg_latency_ms=10.0,
        results=[
            EvalResult(
                case_id="c1",
                prompt="p",
                expected="e",
                actual="a",
                score=1.0,
                passed=True,
                latency_ms=10,
                model="m",
            )
        ],
    )

    class FakeRunner:
        def __init__(self, api_key, model, judge_model, threshold):
            self.api_key = api_key

        def run(self, cases, on_case):
            return fake_run

    monkeypatch.setattr(service, "EvalRunner", FakeRunner)
    result = service.eval_run([], "key", "claude-sonnet-5")
    assert result is fake_run


def test_persist_eval_run_delegates_to_store(monkeypatch):
    monkeypatch.setattr(service, "save_eval_run", lambda run: "/path/to/run.json")
    assert service.persist_eval_run(None) == "/path/to/run.json"


def test_write_eval_output_delegates_to_store(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        service, "write_eval_first_result_json", lambda path, run: seen.update(path=path, run=run)
    )
    service.write_eval_output("out.json", "a-run")
    assert seen == {"path": "out.json", "run": "a-run"}


def test_eval_list_none_when_dir_missing(monkeypatch, tmp_path):
    missing_dir = tmp_path / "does_not_exist"
    monkeypatch.setattr(service, "EVALS_DIR", missing_dir)
    assert service.eval_list() is None


def test_eval_list_delegates_when_dir_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "EVALS_DIR", tmp_path)
    monkeypatch.setattr(service, "load_eval_run_summaries", lambda limit: [{"run_id": "r1"}])
    assert service.eval_list() == [{"run_id": "r1"}]


def test_eval_scaffold_delegates_to_store(monkeypatch):
    seen = {}
    monkeypatch.setattr(service, "write_eval_suite_scaffold", lambda path: seen.update(path=path))
    service.eval_scaffold("scaffold.json")
    assert seen == {"path": "scaffold.json"}

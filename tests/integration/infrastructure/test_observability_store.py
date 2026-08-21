"""tests/test_observability_store.py

Covers infrastructure/local_storage/observability_store.py — disk I/O
for the Cost, Metrics, Observability & Eval bounded context, extracted
2026-08-19 (Phase D, Context #7). claude_observability.py and
claude_eval.py had zero test coverage before this migration; this
closes that gap for the disk-I/O half of both, alongside the
already-covered claude_cost_optimizer.py/claude_metrics.py logs.
"""

import json

import infrastructure.local_storage.observability_store as store
from domain.observability import EvalCase, EvalResult, EvalRun

# ── Cost log ──────────────────────────────────────────────────────────


def test_log_spend_creates_and_appends(tmp_path, monkeypatch):
    log = tmp_path / "cost_log.json"
    monkeypatch.setattr(store, "SPEND_LOG", log)
    store.log_spend("claude-sonnet-5", 100, 50, 1.5, "hello world")
    entries = json.loads(log.read_text())
    assert len(entries) == 1
    assert entries[0]["model"] == "claude-sonnet-5"
    assert entries[0]["cost_usd"] == 1.5


def test_log_spend_caps_at_5000_entries(tmp_path, monkeypatch):
    log = tmp_path / "cost_log.json"
    monkeypatch.setattr(store, "SPEND_LOG", log)
    log.write_text(
        json.dumps(
            [{"ts": "x", "model": "m", "in_tok": 1, "out_tok": 1, "cost_usd": 0.0, "prompt": "p"}] * 5000
        )
    )
    store.log_spend("claude-sonnet-5", 1, 1, 0.1, "new one")
    entries = json.loads(log.read_text())
    assert len(entries) == 5000
    assert entries[-1]["cost_usd"] == 0.1


def test_read_spend_log_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SPEND_LOG", tmp_path / "nope.json")
    assert store.read_spend_log() == []


def test_clear_spend_log_returns_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SPEND_LOG", tmp_path / "nope.json")
    assert store.clear_spend_log() is False


def test_clear_spend_log_returns_true_and_removes(tmp_path, monkeypatch):
    log = tmp_path / "cost_log.json"
    log.write_text("[]")
    monkeypatch.setattr(store, "SPEND_LOG", log)
    assert store.clear_spend_log() is True
    assert not log.exists()


# ── Metrics log ───────────────────────────────────────────────────────


def test_record_metric_not_billed_on_pure_refusal(tmp_path, monkeypatch):
    log = tmp_path / "metrics.jsonl"
    monkeypatch.setattr(store, "METRICS_LOG_PATH", log)
    store.record_metric("claude-sonnet-5", 500_000, 0, 0.8, stop_reason="refusal")
    entry = json.loads(log.read_text().strip())
    assert entry["not_billed"] is True
    assert entry["cost_usd"] == 0.0


def test_load_metrics_log_filters_by_model(tmp_path, monkeypatch):
    log = tmp_path / "metrics.jsonl"
    monkeypatch.setattr(store, "METRICS_LOG_PATH", log)
    store.record_metric("claude-sonnet-5", 100, 100, 0.1)
    store.record_metric("claude-opus-4-8", 100, 100, 0.1)
    entries = store.load_metrics_log(model_filter="claude-opus-4-8")
    assert len(entries) == 1
    assert entries[0]["model"] == "claude-opus-4-8"


def test_write_metrics_export_writes_entries_and_summary(tmp_path):
    out = tmp_path / "export.json"
    store.write_metrics_export(str(out), [{"model": "m"}], {"calls": 1})
    data = json.loads(out.read_text())
    assert data["entries"] == [{"model": "m"}]
    assert data["summary"] == {"calls": 1}


# ── Observability request log ────────────────────────────────────────


def test_log_and_read_observability_request(tmp_path, monkeypatch):
    obs_dir = tmp_path / "observability"
    monkeypatch.setattr(store, "OBS_DIR", obs_dir)
    monkeypatch.setattr(store, "OBS_LOG_FILE", obs_dir / "requests.jsonl")
    store.log_observability_request({"ts": "2026-08-19T00:00:00", "model": "m"})
    records = store.read_observability_logs(hours=999999)
    assert len(records) == 1
    assert records[0]["model"] == "m"


def test_clear_observability_log_returns_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "OBS_LOG_FILE", tmp_path / "nope.jsonl")
    assert store.clear_observability_log() is False


# ── Eval suites & runs ────────────────────────────────────────────────


def test_save_and_load_eval_run_summaries(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "EVALS_DIR", tmp_path)
    run = EvalRun(
        run_id="abc12345",
        model="claude-sonnet-5",
        cases=1,
        passed=1,
        avg_score=1.0,
        avg_latency_ms=50.0,
        results=[
            EvalResult(
                case_id="c1",
                prompt="p",
                expected="e",
                actual="a",
                score=1.0,
                passed=True,
                latency_ms=50,
                model="claude-sonnet-5",
            )
        ],
    )
    path = store.save_eval_run(run)
    assert path.endswith("abc12345.json")
    summaries = store.load_eval_run_summaries()
    assert len(summaries) == 1
    assert summaries[0]["run_id"] == "abc12345"


def test_load_eval_run_summaries_none_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "EVALS_DIR", tmp_path / "does_not_exist")
    assert store.load_eval_run_summaries() is None


def test_load_eval_suite_parses_cases(tmp_path):
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps([{"case_id": "c1", "prompt": "p", "expected": "e"}]))
    cases = store.load_eval_suite(str(suite))
    assert len(cases) == 1
    assert isinstance(cases[0], EvalCase)
    assert cases[0].case_id == "c1"


def test_write_eval_suite_scaffold(tmp_path):
    out = tmp_path / "scaffold.json"
    store.write_eval_suite_scaffold(str(out))
    data = json.loads(out.read_text())
    assert len(data) == 2
    assert data[0]["case_id"] == "greet_01"


def test_write_eval_first_result_json_writes_only_first_result(tmp_path):
    out = tmp_path / "output.json"
    run = EvalRun(
        run_id="abc12345",
        model="claude-sonnet-5",
        cases=2,
        passed=1,
        avg_score=0.5,
        avg_latency_ms=100.0,
        results=[
            EvalResult(
                case_id="c1",
                prompt="p",
                expected="e",
                actual="a",
                score=1.0,
                passed=True,
                latency_ms=50,
                model="m",
            ),
            EvalResult(
                case_id="c2",
                prompt="p",
                expected="e",
                actual="a",
                score=0.0,
                passed=False,
                latency_ms=150,
                model="m",
            ),
        ],
    )
    store.write_eval_first_result_json(str(out), run)
    data = json.loads(out.read_text())
    assert data["case_id"] == "c1"


def test_write_eval_first_result_json_empty_results(tmp_path):
    out = tmp_path / "output.json"
    run = EvalRun(run_id="abc", model="m", cases=0, passed=0, avg_score=0, avg_latency_ms=0, results=[])
    store.write_eval_first_result_json(str(out), run)
    assert json.loads(out.read_text()) == {}

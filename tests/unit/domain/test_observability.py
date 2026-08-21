"""tests/unit/domain/test_observability.py

Covers domain/observability.py — the pure data + logic layer for the
Cost, Metrics, Observability & Eval bounded context, extracted 2026-08-19
(Phase D, Context #7). claude_observability.py and claude_eval.py had
zero test coverage before this migration; this closes that gap for the
pure-logic half of both.
"""

import pytest

from domain.observability import (
    DEFAULT_PRICE,
    PRICE,
    SONNET5_INTRO_PRICE,
    TIER_MODELS,
    EvalCase,
    EvalResult,
    EvalRun,
    OptimizedResponse,
    build_eval_run,
    build_latency_report,
    build_request_record,
    classify_complexity,
    estimate_cost,
    histogram,
    price_lookup,
    select_model,
    summarise_metrics,
)

# ── Cost routing ──────────────────────────────────────────────────────


def test_sonnet5_intro_price_alias_matches_base_price():
    assert SONNET5_INTRO_PRICE == PRICE["claude-sonnet-5"]


def test_estimate_cost_delegates_to_catalog():
    cost = estimate_cost("claude-sonnet-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(PRICE["claude-sonnet-5"]["in"] + PRICE["claude-sonnet-5"]["out"])


def test_estimate_cost_unknown_model_uses_default():
    cost = estimate_cost("claude-unknown-future-model", 1_000_000, 1_000_000)
    assert cost == pytest.approx(DEFAULT_PRICE["in"] + DEFAULT_PRICE["out"])


def test_classify_complexity_tiers():
    assert classify_complexity("hi") == "low"
    assert classify_complexity("word " * 300) == "medium"
    assert classify_complexity("word " * 900) == "high"


def test_classify_complexity_code_markers_bump_tier():
    prompt = "def a():\nclass B:\nfunction c():\nSELECT * \nCREATE TABLE\nCREATE INDEX"
    assert classify_complexity(prompt) == "high"


def test_select_model_force_overrides():
    assert select_model("low", force="claude-opus-4-8") == "claude-opus-4-8"


def test_select_model_maps_tiers():
    assert select_model("low") == TIER_MODELS[0]
    assert select_model("medium") == TIER_MODELS[1]
    assert select_model("high") == TIER_MODELS[2]


def test_optimized_response_is_a_plain_dataclass():
    r = OptimizedResponse(
        text="hi",
        model_used="claude-sonnet-5",
        complexity="low",
        in_tokens=1,
        out_tokens=1,
        cost_usd=0.0,
        latency_ms=1,
    )
    assert r.text == "hi"


# ── Metrics ───────────────────────────────────────────────────────────


def test_price_lookup_matches_catalog_price():
    cost = price_lookup("claude-sonnet-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(PRICE["claude-sonnet-5"]["in"] + PRICE["claude-sonnet-5"]["out"])


def test_summarise_metrics_empty():
    assert summarise_metrics([]) == {"calls": 0}


def test_summarise_metrics_aggregates_by_model():
    entries = [
        {
            "model": "claude-sonnet-5",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 1.0,
            "latency_seconds": 2.0,
        },
        {
            "model": "claude-sonnet-5",
            "input_tokens": 200,
            "output_tokens": 100,
            "cost_usd": 2.0,
            "latency_seconds": 4.0,
        },
        {
            "model": "claude-opus-4-8",
            "input_tokens": 10,
            "output_tokens": 10,
            "cost_usd": 0.5,
            "latency_seconds": 1.0,
        },
    ]
    s = summarise_metrics(entries)
    assert s["calls"] == 3
    assert s["total_cost_usd"] == pytest.approx(3.5)
    assert s["by_model"]["claude-sonnet-5"]["calls"] == 2
    assert s["by_model"]["claude-sonnet-5"]["avg_latency_seconds"] == pytest.approx(3.0)


# ── Observability ─────────────────────────────────────────────────────


def test_histogram_no_data():
    assert histogram([]) == "(no data)"


def test_histogram_all_same_value():
    assert histogram([5.0, 5.0]) == "all values = 5"


def test_histogram_has_a_line_per_bucket():
    lines = histogram([1, 2, 3, 4, 5, 6], buckets=3).split("\n")
    assert len(lines) == 3


def test_build_latency_report_empty_returns_none():
    assert build_latency_report([], hours=24) is None


def test_build_latency_report_aggregates():
    records = [
        {"latency_ms": 100, "model": "claude-sonnet-5"},
        {"latency_ms": 200, "model": "claude-sonnet-5"},
        {"latency_ms": 300, "model": "claude-opus-4-8", "error": "boom"},
    ]
    report = build_latency_report(records, hours=24)
    assert report["count"] == 3
    assert report["error_count"] == 1
    assert report["avg_ms"] == pytest.approx(200.0)
    assert report["by_model"]["claude-sonnet-5"]["calls"] == 2


def test_build_request_record_shapes_a_dict():
    rec = build_request_record("claude-sonnet-5", "a" * 200, "b" * 200, 123, 10, 20, error=None, tags=["t1"])
    assert rec["model"] == "claude-sonnet-5"
    assert len(rec["prompt_preview"]) == 120
    assert len(rec["response_preview"]) == 120
    assert rec["latency_ms"] == 123
    assert rec["tags"] == ["t1"]
    assert "req_id" in rec and "ts" in rec


# ── Eval harness ──────────────────────────────────────────────────────


def test_eval_case_and_result_are_plain_dataclasses():
    c = EvalCase(case_id="c1", prompt="p", expected="e")
    assert c.tags == []
    r = EvalResult(
        case_id="c1", prompt="p", expected="e", actual="a", score=1.0, passed=True, latency_ms=5, model="m"
    )
    assert r.reason == ""


def test_build_eval_run_aggregates_results():
    results = [
        EvalResult(
            case_id="c1",
            prompt="p",
            expected="e",
            actual="a",
            score=1.0,
            passed=True,
            latency_ms=100,
            model="m",
        ),
        EvalResult(
            case_id="c2",
            prompt="p",
            expected="e",
            actual="a",
            score=0.0,
            passed=False,
            latency_ms=200,
            model="m",
        ),
    ]
    run = build_eval_run("run1", "claude-sonnet-5", results)
    assert isinstance(run, EvalRun)
    assert run.cases == 2
    assert run.passed == 1
    assert run.avg_score == pytest.approx(0.5)
    assert run.avg_latency_ms == pytest.approx(150.0)


def test_build_eval_run_empty_results():
    run = build_eval_run("run2", "claude-sonnet-5", [])
    assert run.cases == 0
    assert run.avg_score == 0
    assert run.avg_latency_ms == 0


def test_eval_run_summary_string():
    run = build_eval_run(
        "abc123",
        "claude-sonnet-5",
        [
            EvalResult(
                case_id="c1",
                prompt="p",
                expected="e",
                actual="a",
                score=1.0,
                passed=True,
                latency_ms=100,
                model="m",
            ),
        ],
    )
    s = run.summary()
    assert "abc123" in s and "claude-sonnet-5" in s and "1/1 passed" in s

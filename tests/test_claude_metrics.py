"""tests/test_claude_metrics.py

claude_metrics.py had zero test coverage before this release-gate pass
(2026-08-14) — flagged alongside claude_cost_optimizer.py in
docs/53_release_gate_v1.40.0.md as the reason a stale Sonnet 5 price
($3/$15 instead of the now-permanent $2/$10) went undetected in a third
copy of the same pricing table. Covers _price(), the not_billed/refusal
handling from v1.11.0, and summarise().
"""

import json

import pytest

from domain.models.catalog import DEFAULT_PRICE as _CATALOG_DEFAULT
from domain.models.catalog import PRICE as _CATALOG_PRICE
from domain.observability import price_lookup as _price
from domain.observability import summarise_metrics as summarise
from infrastructure.local_storage import observability_store as _obs_store
from infrastructure.local_storage.observability_store import (
    load_metrics_log,
    record_metric,
)
from interfaces.cli.commands.observability_commands import cmd_metrics_export

# Derived views over the single source-of-truth catalog (were
# claude_metrics.PRICE_TABLE / DEFAULT_PRICE):
PRICE_TABLE = {model_id: (p["in"], p["out"]) for model_id, p in _CATALOG_PRICE.items()}
DEFAULT_PRICE = (_CATALOG_DEFAULT["in"], _CATALOG_DEFAULT["out"])


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Every test gets its own LOG_PATH so nothing touches the real
    ~/.ai-coder/metrics.jsonl or leaks state between tests.

    2026-08-19 Phase D, Context #7 "second repoint" (exec-planning.md §5
    step 5): record()/load_log()/cmd_metrics_export() now resolve
    METRICS_LOG_PATH from infrastructure/local_storage/
    observability_store.py's own module namespace, not from this shim's
    LOG_PATH re-export — patching claude_metrics.LOG_PATH no longer
    reaches that I/O, so the fixture patches the store module directly."""
    log_path = tmp_path / "metrics.jsonl"
    monkeypatch.setattr(_obs_store, "METRICS_LOG_PATH", log_path)
    return log_path


# ── pricing table (2026-08-10 release note: $2/$10 is now permanent) ────


def test_sonnet5_price_table_entry_is_2_10_not_cancelled_3_15():
    assert PRICE_TABLE["claude-sonnet-5"] == (2.0, 10.0)


def test_price_uses_sonnet5_rate():
    cost = _price("claude-sonnet-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(2.0 + 10.0)


def test_price_unknown_model_falls_back_to_default():
    cost = _price("claude-unknown-future-model", 1_000_000, 1_000_000)
    assert cost == pytest.approx(DEFAULT_PRICE[0] + DEFAULT_PRICE[1])


# ── record() / not_billed refusal handling (v1.11.0) ─────────────────


def test_record_writes_priced_entry(isolated_log):
    record_metric("claude-sonnet-5", 1_000_000, 1_000_000, 1.5, command="chat")
    lines = isolated_log.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["model"] == "claude-sonnet-5"
    assert entry["cost_usd"] == pytest.approx(12.0)
    assert entry["not_billed"] is False


def test_record_refusal_with_zero_output_is_not_billed(isolated_log):
    record_metric("claude-sonnet-5", 500_000, 0, 0.8, stop_reason="refusal")
    entry = json.loads(isolated_log.read_text().strip())
    assert entry["not_billed"] is True
    assert entry["cost_usd"] == 0.0


def test_record_refusal_with_nonzero_output_is_still_billed(isolated_log):
    # Only a *pure* refusal (no generated output at all) is documented as
    # not billed -- a refusal after partial output should still be priced.
    record_metric("claude-sonnet-5", 500_000, 100, 0.8, stop_reason="refusal")
    entry = json.loads(isolated_log.read_text().strip())
    assert entry["not_billed"] is False
    assert entry["cost_usd"] > 0.0


# ── load_log() filters ────────────────────────────────────────────────


def test_load_log_empty_when_no_file(isolated_log):
    assert load_metrics_log() == []


def test_load_log_model_filter(isolated_log):
    record_metric("claude-sonnet-5", 100, 100, 0.1)
    record_metric("claude-opus-4-8", 100, 100, 0.1)
    entries = load_metrics_log(model_filter="claude-opus-4-8")
    assert len(entries) == 1
    assert entries[0]["model"] == "claude-opus-4-8"


def test_load_log_skips_malformed_lines(isolated_log):
    isolated_log.parent.mkdir(parents=True, exist_ok=True)
    isolated_log.write_text('not json\n{"model": "claude-sonnet-5", "ts": "x"}\n')
    entries = load_metrics_log()
    assert len(entries) == 1


# ── summarise() ────────────────────────────────────────────────────────


def test_summarise_empty_entries():
    assert summarise([]) == {"calls": 0}


def test_summarise_aggregates_by_model():
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
    s = summarise(entries)
    assert s["calls"] == 3
    assert s["total_cost_usd"] == pytest.approx(3.5)
    assert s["by_model"]["claude-sonnet-5"]["calls"] == 2
    assert s["by_model"]["claude-sonnet-5"]["avg_latency_seconds"] == pytest.approx(3.0)
    assert s["by_model"]["claude-opus-4-8"]["calls"] == 1


# ── cmd_metrics_export ───────────────────────────────────────────────


def test_cmd_metrics_export_writes_entries_and_summary(isolated_log, tmp_path):
    record_metric("claude-sonnet-5", 1000, 1000, 0.5)
    out_path = tmp_path / "export.json"
    cmd_metrics_export(str(out_path))
    data = json.loads(out_path.read_text())
    assert len(data["entries"]) == 1
    assert data["summary"]["calls"] == 1

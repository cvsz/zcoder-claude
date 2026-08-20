"""tests/test_application_models_service.py

Covers application/models_service.py — the use-case layer added 2026-08-14
to close the gap where interfaces/cli/commands/model_commands.py called
infrastructure/anthropic_api/models_gateway.py directly, with no reusable
layer for a future Web UI. These are the same behaviors previously only
reachable through cmd_* (and captured via stdout in
tests/test_claude_models_deprecation.py) — now testable as plain data
in/data out, no print() capture needed.
"""
import pytest

from application.models_service import (
    list_models, get_model_info, scan_for_deprecated_models,
    upgrade_all, run_computer_use, run_adaptive_thinking,
)


# ── list_models ──────────────────────────────────────────────────────────

def test_list_models_live_source(monkeypatch):
    class FakeModelsAPI:
        def __init__(self, api_key): pass
        def list_models(self):
            return [{"id": "claude-sonnet-5", "display_name": "Sonnet 5", "context_window": 1_000_000}]

    monkeypatch.setattr("application.models_service.ModelsAPI", FakeModelsAPI)
    result = list_models("k")
    assert result["source"] == "live"
    assert result["models"][0]["id"] == "claude-sonnet-5"


def test_list_models_falls_back_to_local_catalog_on_runtime_error(monkeypatch):
    class FakeModelsAPI:
        def __init__(self, api_key): pass
        def list_models(self):
            raise RuntimeError("network unreachable")

    monkeypatch.setattr("application.models_service.ModelsAPI", FakeModelsAPI)
    result = list_models("k", include_legacy=True)
    assert result["source"] == "local"
    assert result["error"] == "network unreachable"
    assert "current" in result["tiers"]
    assert result["include_legacy"] is True


def test_list_models_local_fallback_excludes_legacy_by_default(monkeypatch):
    class FakeModelsAPI:
        def __init__(self, api_key): pass
        def list_models(self):
            raise RuntimeError("offline")

    monkeypatch.setattr("application.models_service.ModelsAPI", FakeModelsAPI)
    result = list_models("k", include_legacy=False)
    assert "legacy" not in result["tiers"]


# ── get_model_info ───────────────────────────────────────────────────────

def test_get_model_info_live_success(monkeypatch):
    class FakeModelsAPI:
        def __init__(self, api_key): pass
        def get_model(self, model_id):
            return {"id": model_id, "display_name": "Sonnet 5"}

    monkeypatch.setattr("application.models_service.ModelsAPI", FakeModelsAPI)
    result = get_model_info("claude-sonnet-5", "k")
    assert result["live"]["id"] == "claude-sonnet-5"
    assert result["retired"] is None
    assert result["error"] is None


def test_get_model_info_retired_model_flagged():
    result = get_model_info("claude-opus-4-1-20250805", "k")
    assert result["retired"] is not None
    assert result["retired"]["retired"] == "2026-08-05"


def test_get_model_info_falls_back_to_local_catalog(monkeypatch):
    class FakeModelsAPI:
        def __init__(self, api_key): pass
        def get_model(self, model_id):
            raise RuntimeError("offline")

    monkeypatch.setattr("application.models_service.ModelsAPI", FakeModelsAPI)
    result = get_model_info("claude-sonnet-5", "k")
    assert result["local_fallback"] is not None
    assert result["local_fallback"]["id"] == "claude-sonnet-5"
    assert result["error"] is None


def test_get_model_info_unknown_model_surfaces_error(monkeypatch):
    class FakeModelsAPI:
        def __init__(self, api_key): pass
        def get_model(self, model_id):
            raise RuntimeError("404 not found")

    monkeypatch.setattr("application.models_service.ModelsAPI", FakeModelsAPI)
    result = get_model_info("claude-totally-made-up", "k")
    assert result["local_fallback"] is None
    assert result["error"] == "404 not found"


def test_get_model_info_retired_and_unknown_to_live_api_is_not_an_error(monkeypatch):
    class FakeModelsAPI:
        def __init__(self, api_key): pass
        def get_model(self, model_id):
            raise RuntimeError("400 model retired")

    monkeypatch.setattr("application.models_service.ModelsAPI", FakeModelsAPI)
    result = get_model_info("claude-opus-4-1-20250805", "k")
    assert result["retired"] is not None
    assert result["local_fallback"] is None
    assert result["error"] is None  # retirement record already explains the failure


# ── scan_for_deprecated_models ──────────────────────────────────────────

def test_scan_finds_retired_model_id(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-1-20250805"\n')
    hits = scan_for_deprecated_models(str(tmp_path))
    assert "claude-opus-4-1-20250805" in hits["retired_hits"]
    assert hits["deprecated_hits"] == {}


def test_scan_clean_tree_returns_empty_hits(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-8"\n')
    hits = scan_for_deprecated_models(str(tmp_path))
    assert hits["retired_hits"] == {}
    assert hits["deprecated_hits"] == {}


def test_scan_single_file_path(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-1-20250805"\n')
    hits = scan_for_deprecated_models(str(f))
    assert "claude-opus-4-1-20250805" in hits["retired_hits"]


# ── upgrade_all ──────────────────────────────────────────────────────────

def test_upgrade_all_unknown_target_returns_error():
    result = upgrade_all("/tmp", target="not-a-real-target")
    assert "error" in result


def test_upgrade_all_dry_run_does_not_modify_file(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-1-20250805"\n')
    result = upgrade_all(str(tmp_path), target="fable5", apply=False)
    assert result["applied"] is False
    assert result["total_hits"] == 1
    assert f.read_text() == 'MODEL = "claude-opus-4-1-20250805"\n'  # unchanged


def test_upgrade_all_apply_rewrites_file_and_writes_backup(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-1-20250805"\n')
    result = upgrade_all(str(tmp_path), target="fable5", apply=True)
    assert result["applied"] is True
    assert result["files_changed"] == 1
    assert "claude-fable-5" in f.read_text()
    assert (tmp_path / "config.py.bak").exists()


def test_upgrade_all_apply_no_backup_skips_bak_file(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-1-20250805"\n')
    upgrade_all(str(tmp_path), target="fable5", apply=True, no_backup=True)
    assert not (tmp_path / "config.py.bak").exists()


def test_upgrade_all_no_hits_returns_empty_report(tmp_path):
    f = tmp_path / "config.py"
    f.write_text('MODEL = "not-a-claude-model-id-at-all"\n')
    result = upgrade_all(str(tmp_path), target="fable5", apply=False)
    assert result["per_file_report"] == []


def test_upgrade_all_opus5_target_rewrites_to_current_flagship(tmp_path):
    # Added 2026-08-17: --upgrade-target had no path to Claude Opus 5
    # (released 2026-07-24) — "opus" still pointed at claude-opus-4-8.
    # Regression check that opus5 is wired all the way through.
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-7"\n')
    result = upgrade_all(str(tmp_path), target="opus5", apply=True)
    assert result["target_id"] == "claude-opus-5"
    assert f.read_text() == 'MODEL = "claude-opus-5"\n'


def test_upgrade_all_sonnet5_target_rewrites_to_current_flagship(tmp_path):
    # Added 2026-08-17: --upgrade-target had no path to Claude Sonnet 5 at
    # all, current or legacy IDs both included.
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-sonnet-4-6"\n')
    result = upgrade_all(str(tmp_path), target="sonnet5", apply=True)
    assert result["target_id"] == "claude-sonnet-5"
    assert f.read_text() == 'MODEL = "claude-sonnet-5"\n'


def test_upgrade_all_opus_target_unchanged_for_backward_compat(tmp_path):
    # "opus" intentionally still targets claude-opus-4-8, not claude-opus-5
    # — existing --upgrade-target opus scripts/CI should not silently
    # change behavior just because opus5 now exists as an explicit choice.
    f = tmp_path / "config.py"
    f.write_text('MODEL = "claude-opus-4-6"\n')
    result = upgrade_all(str(tmp_path), target="opus", apply=True)
    assert result["target_id"] == "claude-opus-4-8"


# ── run_computer_use / run_adaptive_thinking ────────────────────────────

def test_run_computer_use_delegates_to_gateway(monkeypatch):
    class FakeComputerUseCoder:
        def __init__(self, api_key, model): pass
        def run_task(self, task):
            return {"text": f"did {task}", "tool_calls": []}

    monkeypatch.setattr("application.models_service.ComputerUseCoder", FakeComputerUseCoder)
    result = run_computer_use("open a file", "k", "claude-sonnet-5")
    assert result["text"] == "did open a file"


def test_run_adaptive_thinking_delegates_to_gateway(monkeypatch):
    class FakeAdaptiveThinkingCoder:
        def __init__(self, api_key, model): pass
        def adaptive(self, prompt, budget, effort):
            return f"[{effort}/{budget}] {prompt}"

    monkeypatch.setattr("application.models_service.AdaptiveThinkingCoder", FakeAdaptiveThinkingCoder)
    result = run_adaptive_thinking("solve this", "k", "claude-sonnet-5", effort="high", budget=16000)
    assert result == "[high/16000] solve this"


def test_run_adaptive_thinking_default_budget_when_none(monkeypatch):
    class FakeAdaptiveThinkingCoder:
        def __init__(self, api_key, model): pass
        def adaptive(self, prompt, budget, effort):
            return budget

    monkeypatch.setattr("application.models_service.AdaptiveThinkingCoder", FakeAdaptiveThinkingCoder)
    assert run_adaptive_thinking("x", "k", "claude-sonnet-5", budget=None) == 8000

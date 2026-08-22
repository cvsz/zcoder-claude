"""tests/test_computer_use_ga.py

Covers the GA computer_toolset_20260801 request shape in
infrastructure/anthropic_api/models_gateway.py (ComputerUseCoder), per
the Aug 19–20 2026 release notes:

- GA needs no beta header; the legacy computer_20251124-era beta shape
  stays available via an explicit opt-in (toolset="legacy").
- GA features: batch actions (several actions per turn), `zoom`
  enabled by default, per-member configuration via `configs`.
- Gating: only Fable 5, Mythos 5, Opus 5, Sonnet 5 and Opus 4.8 may
  use the GA toolset; anything else fails client-side with a clear
  error.

NOTE: shapes here follow the documented GA spec — no live API key is
available in this environment, so every HTTP interaction goes through
a fake urlopen that captures the outgoing request body/headers.
"""

import json
import urllib.request

import pytest

from core.exceptions import ZCoderError
from infrastructure.anthropic_api.models_gateway import (
    COMPUTER_USE_BETA,
    COMPUTER_USE_TOOLSET_GA,
    DEFAULT_COMPUTER_USE_SHAPE,
    ComputerUseCoder,
    computer_use_toolset_for_model,
)


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _install_fake_urlopen(monkeypatch, captured: dict, response_body: dict | None = None):
    """Fake urllib.request.urlopen at the stdlib module (the real call
    site is http_client.urlopen_json) — same pattern as
    tests/test_claude_tools.py."""

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _FakeResp(json.dumps(response_body or {"content": [], "stop_reason": "end_turn"}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def test_default_shape_is_ga():
    # The GA toolset is the new default request shape; legacy stays
    # available but only behind an explicit opt-in.
    assert DEFAULT_COMPUTER_USE_SHAPE == "ga"


def test_run_task_sends_ga_toolset_without_beta_header(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    cu = ComputerUseCoder(api_key="sk-test", model="claude-opus-4-8")

    cu.run_task("open a terminal")

    tools = captured["body"]["tools"]
    assert len(tools) == 1
    assert tools[0]["type"] == COMPUTER_USE_TOOLSET_GA
    assert tools[0]["name"] == "computer"
    # GA feature flags per the release notes: batch actions on, zoom on.
    assert tools[0]["batch_actions"] is True
    assert tools[0]["zoom"] is True
    # Per-member configuration travels in `configs`.
    assert tools[0]["configs"]["bash"]["enabled"] is True
    assert tools[0]["configs"]["text_editor"]["enabled"] is True
    # GA — no beta header on the wire.
    assert "anthropic-beta" not in captured["headers"]
    assert "anthropic-version" in captured["headers"]


def test_ga_toolset_respects_custom_dimensions(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    cu = ComputerUseCoder(api_key="sk-test", model="claude-sonnet-5", width=1280, height=800)

    cu.run_task("screenshot")

    tool = captured["body"]["tools"][0]
    assert tool["display_width_px"] == 1280
    assert tool["display_height_px"] == 800


def test_ga_configs_override_replaces_defaults(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    custom: dict = {"bash": {"enabled": False}}
    cu = ComputerUseCoder(api_key="sk-test", model="claude-fable-5", configs=custom)

    cu.run_task("edit a file")

    assert captured["body"]["tools"][0]["configs"] == custom


def test_batch_actions_response_returns_every_action_in_order(monkeypatch):
    # GA batch actions: one assistant turn may carry several tool_use
    # blocks; run_task must surface all of them, preserving order.
    captured = {}
    response = {
        "content": [
            {"type": "text", "text": "clicking then typing"},
            {"type": "tool_use", "id": "a1", "name": "computer", "input": {"action": "screenshot"}},
            {"type": "tool_use", "id": "a2", "name": "bash", "input": {"command": "ls"}},
        ],
        "stop_reason": "tool_use",
    }
    _install_fake_urlopen(monkeypatch, captured, response)
    cu = ComputerUseCoder(api_key="sk-test", model="claude-mythos-5")

    result = cu.run_task("do two things")

    assert [tc["id"] for tc in result["tool_calls"]] == ["a1", "a2"]
    assert result["tool_calls"][0]["input"] == {"action": "screenshot"}
    assert result["tool_calls"][1]["input"] == {"command": "ls"}
    assert result["text"] == "clicking then typing"
    assert result["stop_reason"] == "tool_use"


def test_ga_toolset_unsupported_model_raises_client_side():
    with pytest.raises(ZCoderError) as exc:
        computer_use_toolset_for_model("claude-sonnet-4-5")
    msg = str(exc.value)
    assert "claude-sonnet-4-5" in msg
    assert COMPUTER_USE_TOOLSET_GA in msg
    # The error names the supported set so the caller can self-serve.
    for mid in ("claude-fable-5", "claude-mythos-5", "claude-opus-5", "claude-sonnet-5", "claude-opus-4-8"):
        assert mid in msg


def test_ga_supported_models_all_pass_gating():
    for mid in ("claude-fable-5", "claude-mythos-5", "claude-opus-5", "claude-sonnet-5", "claude-opus-4-8"):
        tool = computer_use_toolset_for_model(mid)
        assert tool["type"] == COMPUTER_USE_TOOLSET_GA


def test_unsupported_model_fails_before_any_http_call(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)

    with pytest.raises(ZCoderError):
        ComputerUseCoder(api_key="sk-test", model="claude-haiku-4-5").run_task("x")

    assert "body" not in captured  # nothing went out on the wire


def test_legacy_opt_in_keeps_beta_header_and_dated_tools(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    cu = ComputerUseCoder(api_key="sk-test", model="claude-sonnet-4-5", toolset="legacy")

    cu.run_task("old shape")

    types = [t["type"] for t in captured["body"]["tools"]]
    assert types == ["computer_20250124", "bash_20250124", "text_editor_20250124"]
    assert captured["headers"].get("anthropic-beta") == COMPUTER_USE_BETA


def test_unknown_toolset_value_is_rejected():
    with pytest.raises(ValueError):
        ComputerUseCoder(api_key="sk-test", model="claude-sonnet-5", toolset="beta")

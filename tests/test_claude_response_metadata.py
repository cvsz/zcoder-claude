"""tests/test_claude_response_metadata.py

Covers claude_response_metadata.py — the anthropic-workspace-id /
anthropic-organization-id response header lookup (release-gate audit,
2026-08-14). Request-capture tests assert against
resilience.urlopen_json_with_headers rather than a hand-invented mock
shape, and cover both header-casing variants since urllib doesn't
guarantee case normalization across platforms.

Clean Architecture note (2026-08-21 migration): the implementation now
lives in infrastructure/anthropic_api/model_wrappers_gateway.py (the
claude_response_metadata.py name is a compatibility shim), so module-level
monkeypatches target the DEFINING module (`gw`) — patching the shim would
set attributes the real code never reads. Instance-level patches need no
repointing anywhere in this suite.
"""

import json

import infrastructure.anthropic_api.model_wrappers_gateway as gw
from core.exceptions import ZCoderError
from infrastructure.anthropic_api.model_wrappers_gateway import get_response_metadata
from interfaces.cli.commands.wrapper_commands import cmd_whoami


def test_get_response_metadata_parses_lowercase_headers(monkeypatch):
    def fake_call(api_key):
        return {"content": []}, {"anthropic-workspace-id": "wrkspc_1", "anthropic-organization-id": "org_1"}

    monkeypatch.setattr(gw, "_call_with_headers", fake_call)
    meta = get_response_metadata("sk-ant-fake")
    assert meta.workspace_id == "wrkspc_1"
    assert meta.organization_id == "org_1"


def test_get_response_metadata_parses_titlecase_headers(monkeypatch):
    def fake_call(api_key):
        return {"content": []}, {"Anthropic-Workspace-Id": "wrkspc_2", "Anthropic-Organization-Id": "org_2"}

    monkeypatch.setattr(gw, "_call_with_headers", fake_call)
    meta = get_response_metadata("sk-ant-fake")
    assert meta.workspace_id == "wrkspc_2"
    assert meta.organization_id == "org_2"


def test_get_response_metadata_missing_headers_are_none(monkeypatch):
    monkeypatch.setattr(gw, "_call_with_headers", lambda api_key: ({"content": []}, {}))
    meta = get_response_metadata("sk-ant-fake")
    assert meta.workspace_id is None
    assert meta.organization_id is None


def test_call_with_headers_sends_minimal_documented_payload(monkeypatch):
    """Request-capture test: asserts the real request shape (endpoint,
    model, max_tokens) rather than trusting a hand-rolled mock."""
    captured = {}

    def fake_urlopen_json_with_headers(req, timeout):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode())
        captured["headers"] = dict(req.headers)
        return {"content": []}, {"anthropic-workspace-id": "wrkspc_3"}

    monkeypatch.setattr(gw, "urlopen_json_with_headers", fake_urlopen_json_with_headers)
    meta = get_response_metadata("sk-ant-fake")

    assert captured["url"] == gw.MESSAGES_ENDPOINT
    assert captured["payload"]["model"] == gw._WHOAMI_MODEL
    assert captured["payload"]["max_tokens"] == 1
    assert captured["headers"]["X-api-key"] == "sk-ant-fake"
    assert meta.workspace_id == "wrkspc_3"


def test_cmd_whoami_prints_ids(monkeypatch, capsys):
    monkeypatch.setattr(
        gw,
        "_call_with_headers",
        lambda api_key: (
            {"content": []},
            {"anthropic-workspace-id": "wrkspc_4", "anthropic-organization-id": "org_4"},
        ),
    )
    cmd_whoami("sk-ant-fake")
    out = capsys.readouterr().out
    assert "wrkspc_4" in out
    assert "org_4" in out


def test_cmd_whoami_handles_error(monkeypatch, capsys):
    def raise_error(api_key):
        raise ZCoderError("bad key")

    monkeypatch.setattr(gw, "_call_with_headers", raise_error)
    result = cmd_whoami("sk-ant-bad")
    assert result is None
    assert "ERROR" in capsys.readouterr().out

"""tests/test_claude_code_context_editing.py

Covers the --agent-context-editing wiring described in claude_code.py:
  - CodeAgent.query(): when a context_management payload is passed in,
    it rides along on the Messages payload and CONTEXT_MANAGEMENT_BETA
    is sent as an anthropic-beta header; when omitted (the default),
    neither shows up, so existing callers are unaffected.
  - cmd_code_agent(): the agent_context_editing flag builds the payload
    via claude_tools.build_context_management(clear_tool_uses=True) and
    forwards it into agent.query() as context_management.
"""

import pytest

from claude_code import CodeAgent, CodeSession, cmd_code_agent
from claude_tools import CONTEXT_MANAGEMENT_BETA, build_context_management

# cmd_code_agent now lives in interfaces/cli/commands/code_agent_loop_commands.py
# and imports CodeAgent from infrastructure/anthropic_api/code_agent_loop_gateway.py
# at module load time — patching "claude_code.CodeAgent" (the shim's
# re-exported name) has no effect on that module's own local `CodeAgent`
# reference. Same "second repoint" pattern as every other migrated
# module (see exec-planning.md §5 step 5).
_CMD_CODE_AGENT_MODULE = "interfaces.cli.commands.code_agent_loop_commands"


@pytest.fixture(autouse=True)
def isolated_sessions_dir(tmp_path, monkeypatch):
    """Keep CodeSession.save() out of the real ~/.ai-coder directory.

    CodeSession is now defined in infrastructure/local_storage/
    code_agent_store.py, so SESSIONS_DIR must be patched there — that's
    where CodeSession.save()/load() resolve the name from
    (module-level global), not wherever the class happens to be
    re-imported into (claude_code.py's shim, or this test file).
    """
    monkeypatch.setattr("infrastructure.local_storage.code_agent_store.SESSIONS_DIR", tmp_path)


def _end_turn_response(text="ok"):
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


# ── CodeAgent.query() ────────────────────────────────────────────────────


def test_query_without_context_management_omits_payload_and_betas(monkeypatch):
    agent = CodeAgent(api_key="k", model="claude-sonnet-5")
    session = CodeSession(cwd=".", model="claude-sonnet-5")
    captured = {}

    def fake_post(payload, betas=None):
        captured["payload"] = payload
        captured["betas"] = betas
        return _end_turn_response()

    monkeypatch.setattr(agent, "_post", fake_post)
    agent.query("hi", session, tools="none", output_mode="text")

    assert "context_management" not in captured["payload"]
    assert captured["betas"] is None


def test_query_with_context_management_attaches_payload_and_beta(monkeypatch):
    agent = CodeAgent(api_key="k", model="claude-sonnet-5")
    session = CodeSession(cwd=".", model="claude-sonnet-5")
    cm = build_context_management(clear_tool_uses=True)
    captured = {}

    def fake_post(payload, betas=None):
        captured["payload"] = payload
        captured["betas"] = betas
        return _end_turn_response()

    monkeypatch.setattr(agent, "_post", fake_post)
    agent.query("hi", session, tools="none", output_mode="text", context_management=cm)

    assert captured["payload"]["context_management"] == cm
    assert captured["betas"] == [CONTEXT_MANAGEMENT_BETA]


def test_query_context_management_survives_multiple_turns(monkeypatch):
    """The context_management payload and beta header should be resent
    on every turn of the loop, not just the first."""
    agent = CodeAgent(api_key="k", model="claude-sonnet-5")
    session = CodeSession(cwd=".", model="claude-sonnet-5")
    cm = build_context_management(clear_tool_uses=True)
    calls = []

    def fake_post(payload, betas=None):
        calls.append((payload, betas))
        if len(calls) == 1:
            return {
                "content": [{"type": "tool_use", "id": "t1", "name": "LS", "input": {}}],
                "stop_reason": "tool_use",
                "usage": {},
            }
        return _end_turn_response("done")

    monkeypatch.setattr(agent, "_post", fake_post)
    agent.query("hi", session, tools="all", output_mode="text", context_management=cm)

    assert len(calls) == 2
    for payload, betas in calls:
        assert payload["context_management"] == cm
        assert betas == [CONTEXT_MANAGEMENT_BETA]


# ── cmd_code_agent() wiring ──────────────────────────────────────────────


def test_cmd_code_agent_flag_off_passes_no_context_management(monkeypatch, tmp_path):
    captured = {}

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, **kwargs):
            captured.update(kwargs)
            return "result"

    monkeypatch.setattr(f"{_CMD_CODE_AGENT_MODULE}.CodeAgent", FakeAgent)

    cmd_code_agent(
        prompt="do a thing",
        api_key="k",
        model="claude-sonnet-5",
        cwd=str(tmp_path),
        headless=True,
    )

    assert captured["context_management"] is None


def test_cmd_code_agent_flag_on_builds_and_forwards_context_management(monkeypatch, tmp_path):
    captured = {}

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, **kwargs):
            captured.update(kwargs)
            return "result"

    monkeypatch.setattr(f"{_CMD_CODE_AGENT_MODULE}.CodeAgent", FakeAgent)

    cmd_code_agent(
        prompt="do a thing",
        api_key="k",
        model="claude-sonnet-5",
        cwd=str(tmp_path),
        headless=True,
        agent_context_editing=True,
    )

    expected = build_context_management(clear_tool_uses=True)
    assert captured["context_management"] == expected
    # Sanity check this is really the clear_tool_uses edit and not compact.
    edit_types = [e["type"] for e in captured["context_management"]["edits"]]
    assert "clear_tool_uses_20250919" in edit_types
    assert "compact_20260112" not in edit_types


def test_cmd_code_agent_headless_forces_text_output_mode(monkeypatch, tmp_path, capsys):
    captured = {}

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, **kwargs):
            captured.update(kwargs)
            return "result"

    monkeypatch.setattr(f"{_CMD_CODE_AGENT_MODULE}.CodeAgent", FakeAgent)

    cmd_code_agent(
        prompt="do a thing",
        api_key="k",
        model="claude-sonnet-5",
        cwd=str(tmp_path),
        headless=True,
        output_mode="stream",
    )

    # headless always forces "text", regardless of the requested output_mode
    assert captured["output_mode"] == "text"
    out = capsys.readouterr().out
    assert "result" in out

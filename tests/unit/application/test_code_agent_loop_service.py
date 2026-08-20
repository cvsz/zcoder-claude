"""tests/unit/application/test_code_agent_loop_service.py

Covers application/code_agent_loop_service.py — the use-case layer for
the previously-deferred part of Agent Execution & Code (sessions,
hooks, MCP, subagents, skills, todos, memory, the main agentic query
loop), migrated 2026-08-17. Fake gateway/store classes substituted in —
no print() capture, no real network, no real filesystem outside
tmp_path/monkeypatched env vars.
"""
import json

import application.code_agent_loop_service as service


# ── Session lifecycle ────────────────────────────────────────────────────

def test_load_or_create_session_no_id_creates_new():
    session, resumed = service.load_or_create_session(None, ".", "claude-sonnet-5",
                                                        "askPermission", None)
    assert resumed is False
    assert session.model == "claude-sonnet-5"


def test_load_or_create_session_existing_id_resumes(monkeypatch):
    class FakeSession:
        id = "abc123"
        turns = [1, 2]

    monkeypatch.setattr(service, "CodeSession", type("S", (), {
        "load": staticmethod(lambda sid: FakeSession()),
    }))
    session, resumed = service.load_or_create_session("abc123", ".", "claude-sonnet-5",
                                                        "askPermission", None)
    assert resumed is True
    assert session.id == "abc123"


def test_load_or_create_session_missing_id_falls_back_to_new(monkeypatch):
    def raise_not_found(sid):
        raise FileNotFoundError()

    real_session_cls = service.CodeSession

    class FakeSessionCls:
        load = staticmethod(raise_not_found)

        def __init__(self, session_id=None, cwd=".", model="claude-sonnet-5",
                     permission_mode="askPermission", system_prompt=""):
            self.id = session_id
            self.cwd = cwd

    monkeypatch.setattr(service, "CodeSession", FakeSessionCls)
    session, resumed = service.load_or_create_session("missing-id", ".", "claude-sonnet-5",
                                                        "askPermission", None)
    assert resumed is False
    assert session.id == "missing-id"
    monkeypatch.setattr(service, "CodeSession", real_session_cls)


# ── Output style ─────────────────────────────────────────────────────────

def test_apply_output_style_appends_fragment(monkeypatch):
    import sys
    import types

    fake_mod = types.ModuleType("claude_output_styles")
    fake_mod.system_prompt_fragment = lambda name: f"[{name} style]"
    monkeypatch.setitem(sys.modules, "claude_output_styles", fake_mod)

    session = service.CodeSession(cwd=".", model="claude-sonnet-5")
    session.system_prompt = "base"
    service.apply_output_style(session, "concise")
    assert session.system_prompt == "base\n\n[concise style]"


def test_apply_output_style_missing_module_is_noop(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "claude_output_styles":
            raise ImportError()
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    session = service.CodeSession(cwd=".", model="claude-sonnet-5")
    session.system_prompt = "base"
    service.apply_output_style(session, "concise")
    assert session.system_prompt == "base"


# ── Sandbox / plugin bins ────────────────────────────────────────────────

def test_enable_sandbox_sets_env_vars(monkeypatch, tmp_path):
    monkeypatch.delenv("AI_CODER_SANDBOX", raising=False)
    monkeypatch.delenv("AI_CODER_SANDBOX_NET", raising=False)
    monkeypatch.delenv("AI_CODER_SANDBOX_ROOTS", raising=False)

    service.enable_sandbox(str(tmp_path), allow_net=True, extra_roots=["/extra"])

    import os
    assert os.environ["AI_CODER_SANDBOX"] == "1"
    assert os.environ["AI_CODER_SANDBOX_NET"] == "1"
    roots = json.loads(os.environ["AI_CODER_SANDBOX_ROOTS"])
    assert str(tmp_path.resolve()) in roots
    assert "/extra" in roots


def test_enable_sandbox_net_blocked_by_default(monkeypatch, tmp_path):
    service.enable_sandbox(str(tmp_path), allow_net=False)
    import os
    assert os.environ["AI_CODER_SANDBOX_NET"] == "0"


# ── Context editing ──────────────────────────────────────────────────────

def test_build_agent_context_editing_disabled_returns_none():
    assert service.build_agent_context_editing(False) is None


def test_build_agent_context_editing_enabled_builds_clear_tool_uses():
    cm = service.build_agent_context_editing(True)
    assert cm is not None
    edit_types = [e["type"] for e in cm["edits"]]
    assert "clear_tool_uses_20250919" in edit_types


# ── Agent query orchestration ────────────────────────────────────────────

def test_run_agent_query_forwards_all_args_and_callbacks():
    captured = {}

    class FakeAgent:
        def query(self, **kwargs):
            captured.update(kwargs)
            return "final text"

    result = service.run_agent_query(
        FakeAgent(), "do it", session=object(), tools="all", permission="askPermission",
        hooks=object(), output_mode="stream", context_management=None,
        on_text=lambda t: None,
    )
    assert result == "final text"
    assert captured["prompt"] == "do it"
    assert captured["tools"] == "all"
    assert captured["permission"] == "askPermission"
    assert captured["output_mode"] == "stream"
    assert "on_text" in captured
    assert captured["can_use_tool"] is service.default_can_use_tool


def test_run_subagent_uses_safe_tools_and_accept_edits(monkeypatch, tmp_path):
    captured = {}

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, prompt, session, tools, permission, output_mode, **callbacks):
            captured["tools"] = tools
            captured["permission"] = permission
            captured["prompt"] = prompt
            return "subagent result"

    monkeypatch.setattr(service, "CodeAgent", FakeAgent)
    result = service.run_subagent("do the sub-task", "k", "claude-sonnet-5", cwd=str(tmp_path))
    assert result == "subagent result"
    assert captured["tools"] == "safe"
    assert captured["permission"] == "acceptEdits"
    assert captured["prompt"] == "do the sub-task"


# ── Todo generation (both outcomes) ──────────────────────────────────────

def test_generate_todos_parses_json_array(monkeypatch, tmp_path):
    monkeypatch.setattr("infrastructure.local_storage.code_agent_store.TODO_FILE",
                         tmp_path / "todos.json")

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, *a, **k):
            return 'Sure, here you go: ["write tests", "fix bug"]'

    monkeypatch.setattr(service, "CodeAgent", FakeAgent)
    items, raw_on_error = service.generate_todos("build a feature", "k", "claude-sonnet-5")
    assert raw_on_error is None
    assert [i["text"] for i in items] == ["write tests", "fix bug"]


def test_generate_todos_no_match_returns_nothing_silently(monkeypatch, tmp_path):
    """Matches the original's exact (arguably surprising) behavior: if
    the response contains no '[...]' at all, nothing is printed and
    nothing is added — this is neither a match nor an exception."""
    monkeypatch.setattr("infrastructure.local_storage.code_agent_store.TODO_FILE",
                         tmp_path / "todos.json")

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, *a, **k):
            return "I couldn't come up with a list."

    monkeypatch.setattr(service, "CodeAgent", FakeAgent)
    items, raw_on_error = service.generate_todos("vague task", "k", "claude-sonnet-5")
    assert items == []
    assert raw_on_error is None


def test_generate_todos_malformed_json_returns_raw_text(monkeypatch, tmp_path):
    monkeypatch.setattr("infrastructure.local_storage.code_agent_store.TODO_FILE",
                         tmp_path / "todos.json")

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, *a, **k):
            return "Here: [not valid json]"

    monkeypatch.setattr(service, "CodeAgent", FakeAgent)
    items, raw_on_error = service.generate_todos("task", "k", "claude-sonnet-5")
    assert items == []
    assert raw_on_error == "Here: [not valid json]"


# ── Slash-command helpers ────────────────────────────────────────────────

def test_find_custom_command_in_commands_dir(tmp_path, monkeypatch):
    commands_dir = tmp_path / ".claude" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "review.md").write_text("Do a code review.")
    monkeypatch.chdir(tmp_path)

    found = service.find_custom_command("review")
    assert found is not None
    assert found["source"] == "custom"
    assert found["content"] == "Do a code review."


def test_find_custom_command_not_found_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert service.find_custom_command("nonexistent") is None


def test_run_custom_command_combines_content_and_prompt(monkeypatch, tmp_path):
    captured = {}

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def query(self, prompt, session, tools, permission, **callbacks):
            captured["prompt"] = prompt
            captured["tools"] = tools
            captured["permission"] = permission
            return "done"

    monkeypatch.setattr(service, "CodeAgent", FakeAgent)
    service.run_custom_command("Review this code", "focus on security", "k",
                                "claude-sonnet-5", str(tmp_path))
    assert captured["prompt"] == "Review this code\n\nfocus on security"
    assert captured["tools"] == "code"
    assert captured["permission"] == "acceptEdits"


# ── Session listing / diagnostics ────────────────────────────────────────

def test_list_session_files_skips_unparseable(tmp_path, monkeypatch):
    # list_session_files() resolves SESSIONS_DIR from application/
    # code_agent_loop_service.py's own module namespace (imported
    # directly from domain.code_agent) — a separate import site from
    # the one CodeSession.save()/load() use in infrastructure/
    # local_storage/code_agent_store.py, so it needs its own patch.
    monkeypatch.setattr(service, "SESSIONS_DIR", tmp_path)
    (tmp_path / "good.json").write_text(json.dumps({"id": "good"}))
    (tmp_path / "bad.json").write_text("{not valid json")

    rows = service.list_session_files()
    assert len(rows) == 1
    assert rows[0]["id"] == "good"


def test_run_diagnostics_returns_bool_checks(monkeypatch):
    checks = service.run_diagnostics()
    names = [name for name, ok in checks]
    assert "ANTHROPIC_API_KEY set" in names
    assert all(isinstance(ok, bool) for _, ok in checks)

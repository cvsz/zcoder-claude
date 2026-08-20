"""tests/unit/application/test_agents_service.py

Covers application/agents_service.py — the use-case layer added in Phase A
(exec-planing.md) to close the gap where
interfaces/cli/commands/agent_commands.py called ManagedAgentsClient
directly. This is the last of the 3 modules in Phase A (Admin API,
Compliance API done earlier). Focuses on the two functions with real
orchestration logic (run_managed_agent_task, run_multiagent_review) plus
representative coverage of the thin wrappers.
"""
import pytest
from unittest.mock import MagicMock

import application.agents_service as svc


# ── run_managed_agent_task orchestration ────────────────────────────────

def test_run_managed_agent_task_plain_task_sequence(monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)

    result = svc.run_managed_agent_task("do the thing", "sk-test")

    mac.create_agent.assert_called_once()
    mac.create_environment.assert_called_once()
    mac.create_memory_store.assert_not_called()
    mac.create_session.assert_called_once_with(
        "agent_1", "env_1", title="do the thing", memory_store_id=None,
        vault_ids=None, agent_overrides=None, budget_usd_cents=None,
    )
    # run_task now also receives an on_delta callback (agents_gateway.py
    # print()-removal fix) — assert on the args/kwargs that matter rather
    # than exact-call equality, same reasoning as
    # tests/test_claude_agents_sdk.py's equivalent assertion, so this
    # doesn't churn every time a new optional kwarg is threaded through.
    mac.run_task.assert_called_once()
    call_args, call_kwargs = mac.run_task.call_args
    assert call_args == ("sess_1", "do the thing")
    assert call_kwargs["stream_deltas"] is False
    assert callable(call_kwargs["on_delta"])
    assert result["_mode"] == "task"
    assert result["_session"] == {"id": "sess_1"}


def test_run_managed_agent_task_with_memory_store_creates_it_first(monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_memory_store.return_value = {"id": "store_1", "name": "notes"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)

    svc.run_managed_agent_task("task", "sk-test", memory_store="notes")

    mac.create_memory_store.assert_called_once_with(name="notes")
    _, kwargs = mac.create_session.call_args
    assert kwargs["memory_store_id"] == "store_1"


def test_run_managed_agent_task_outcome_mode_skips_run_task(monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.wait_for_outcome.return_value = {"text": "done", "result": "satisfied"}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)

    result = svc.run_managed_agent_task(
        "unused", "sk-test", outcome_description="Build a report",
        outcome_rubric="## has a table", outcome_max_iterations=7,
    )

    mac.define_outcome.assert_called_once_with(
        "sess_1", "Build a report",
        rubric_text="## has a table", rubric_file_id=None, max_iterations=7,
    )
    mac.run_task.assert_not_called()
    assert result["_mode"] == "outcome"


def test_run_managed_agent_task_on_step_callback_fires_for_each_stage(monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)

    events = []
    svc.run_managed_agent_task("task", "sk-test", on_step=lambda e, d: events.append(e))
    assert events == ["agent_created", "env_created", "session_created"]


def test_run_managed_agent_task_works_with_no_callback(monkeypatch):
    """on_step is optional -- must not raise when omitted (headless/Web use)."""
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)
    svc.run_managed_agent_task("task", "sk-test")  # no on_step kwarg


# ── run_multiagent_review orchestration ──────────────────────────────────

def test_run_multiagent_review_rejects_unknown_specialist():
    with pytest.raises(ValueError, match="Unknown specialist"):
        svc.run_multiagent_review("/repo", ["not-a-real-specialist"], "sk-test")


def test_run_multiagent_review_creates_one_agent_per_specialist_plus_coordinator(monkeypatch):
    mac = MagicMock()
    mac.create_agent.side_effect = [
        {"id": "spec_1"}, {"id": "spec_2"}, {"id": "coordinator_1"},
    ]
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "combined report"}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)

    from domain.agents.agent_config import REVIEW_SPECIALIST_PRESETS
    specialists = list(REVIEW_SPECIALIST_PRESETS)[:2]
    result = svc.run_multiagent_review("/repo", specialists, "sk-test")

    assert mac.create_agent.call_count == 3  # 2 specialists + 1 coordinator
    mac.create_session.assert_called_once()
    assert result["text"] == "combined report"
    assert result["_session"] == {"id": "sess_1"}


def test_run_multiagent_review_on_step_fires_for_each_specialist_and_session(monkeypatch):
    mac = MagicMock()
    mac.create_agent.side_effect = [{"id": "spec_1"}, {"id": "coordinator_1"}]
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "report"}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)

    from domain.agents.agent_config import REVIEW_SPECIALIST_PRESETS
    one_specialist = list(REVIEW_SPECIALIST_PRESETS)[:1]

    events = []
    svc.run_multiagent_review("/repo", one_specialist, "sk-test",
                              on_step=lambda e, d: events.append(e))
    assert events == ["specialist_created", "session_created"]


# ── thin wrappers (representative sample) ────────────────────────────────

def test_create_memory_store_forwards_name(monkeypatch):
    mac = MagicMock()
    mac.create_memory_store.return_value = {"id": "store_1"}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)
    svc.create_memory_store("k", "my-store")
    mac.create_memory_store.assert_called_once_with(name="my-store")


def test_list_memories_forwards_all_filters(monkeypatch):
    mac = MagicMock()
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)
    svc.list_memories("k", "store_1", path_prefix="docs/", depth=1, limit=10)
    mac.list_memories.assert_called_once_with(
        "store_1", path_prefix="docs/", depth=1, limit=10)


def test_add_vault_credential_never_needs_secret_logged(monkeypatch):
    mac = MagicMock()
    mac.add_credential.return_value = {"id": "cred_1"}
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)
    svc.add_vault_credential("k", "vault_1", "static_bearer", secret_value="super-secret")
    args, kwargs = mac.add_credential.call_args
    assert kwargs["secret_value"] == "super-secret"  # passed through, not logged/returned


def test_get_agent_session_forwards_session_id(monkeypatch):
    mac = MagicMock()
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)
    svc.get_agent_session("k", "sess_1")
    mac.get_session.assert_called_once_with("sess_1")


def test_set_session_budget_forwards_cents(monkeypatch):
    mac = MagicMock()
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)
    svc.set_session_budget("k", "sess_1", 2500)
    mac.update_session_budget.assert_called_once_with("sess_1", budget_usd_cents=2500)


def test_remove_session_budget_passes_none(monkeypatch):
    mac = MagicMock()
    monkeypatch.setattr(svc, "ManagedAgentsClient", lambda api_key: mac)
    svc.remove_session_budget("k", "sess_1")
    mac.update_session_budget.assert_called_once_with("sess_1", budget_usd_cents=None)


# ── local (non-Managed-Agents) chat/orchestrate ──────────────────────────

def test_local_agent_chat_new_session_when_no_session_id(monkeypatch):
    fake_agent = MagicMock()
    fake_agent.chat.return_value = "the answer"
    monkeypatch.setattr(svc, "ManagedAgent", lambda api_key, model: fake_agent)
    outcome = svc.local_agent_chat("hi", "k", "claude-sonnet-5")
    assert outcome["status"] == "created_new"
    assert outcome["result"] == "the answer"


def test_local_agent_chat_resumes_existing_session(monkeypatch):
    fake_session = MagicMock(history=[])
    monkeypatch.setattr(svc.AgentSession, "load", staticmethod(lambda sid: fake_session))
    fake_agent = MagicMock()
    fake_agent.chat.return_value = "resumed answer"
    monkeypatch.setattr(svc, "ManagedAgent", lambda api_key, model: fake_agent)
    outcome = svc.local_agent_chat("hi again", "k", "claude-sonnet-5", session_id="abc123")
    assert outcome["status"] == "resumed"


def test_local_agent_chat_creates_with_given_id_when_not_found(monkeypatch):
    def raise_not_found(sid):
        raise FileNotFoundError()
    monkeypatch.setattr(svc.AgentSession, "load", staticmethod(raise_not_found))
    fake_agent = MagicMock()
    fake_agent.chat.return_value = "new with id"
    monkeypatch.setattr(svc, "ManagedAgent", lambda api_key, model: fake_agent)
    outcome = svc.local_agent_chat("hi", "k", "claude-sonnet-5", session_id="missing-id")
    assert outcome["status"] == "created_with_id"
    assert outcome["session"].id == "missing-id"


def test_local_agent_chat_new_flag_forces_new_even_with_session_id(monkeypatch):
    fake_agent = MagicMock()
    fake_agent.chat.return_value = "forced new"
    monkeypatch.setattr(svc, "ManagedAgent", lambda api_key, model: fake_agent)
    outcome = svc.local_agent_chat("hi", "k", "claude-sonnet-5", session_id="abc", new=True)
    assert outcome["status"] == "created_new"


def test_list_local_sessions_returns_parsed_dicts(monkeypatch, tmp_path):
    monkeypatch.setattr(svc, "SESSIONS_DIR", tmp_path)
    (tmp_path / "s1.json").write_text('{"id": "s1", "history": []}')
    (tmp_path / "s2.json").write_text('{"id": "s2", "history": [1, 2]}')
    result = svc.list_local_sessions(max_results=20)
    ids = {r["id"] for r in result}
    assert ids == {"s1", "s2"}


def test_list_local_sessions_skips_malformed_json(monkeypatch, tmp_path):
    monkeypatch.setattr(svc, "SESSIONS_DIR", tmp_path)
    (tmp_path / "bad.json").write_text('not valid json')
    (tmp_path / "good.json").write_text('{"id": "good"}')
    result = svc.list_local_sessions()
    assert len(result) == 1
    assert result[0]["id"] == "good"


def test_list_local_sessions_respects_max_results(monkeypatch, tmp_path):
    monkeypatch.setattr(svc, "SESSIONS_DIR", tmp_path)
    for i in range(5):
        (tmp_path / f"s{i}.json").write_text(f'{{"id": "s{i}"}}')
    result = svc.list_local_sessions(max_results=2)
    assert len(result) == 2

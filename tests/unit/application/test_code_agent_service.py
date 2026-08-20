"""tests/unit/application/test_code_agent_service.py

Covers application/code_agent_service.py — the use-case layer added
2026-08-16 (Phase C) for the tractable part of the Agent Execution &
Code bounded context (Code Execution tool, Hooks, Permissions, Plan
Mode, Multi-Agent Router). Fake gateway/store classes substituted in —
no print() capture, no real network, no real filesystem outside tmp_path.
"""
import application.code_agent_service as service
from domain.agent_execution import HookEvent, Decision, Plan, PlanStep


# ── Code Execution tool ──────────────────────────────────────────────────

def test_run_code_exec_delegates(monkeypatch):
    class FakeCoder:
        def __init__(self, api_key, model, code_exec_version):
            pass

        def execute(self, prompt, file_ids=None, output_dir=None, on_file_saved=None):
            return {"text": "done", "outputs": [], "files": []}

    monkeypatch.setattr(service, "CodeExecutionCoder", FakeCoder)
    result = service.run_code_exec("q", "k", "claude-sonnet-5")
    assert result["text"] == "done"


def test_debug_code_reads_file_and_infers_language(tmp_path, monkeypatch):
    f = tmp_path / "buggy.py"
    f.write_text("print('oops'")
    calls = {}

    class FakeCoder:
        def __init__(self, api_key, model, code_exec_version):
            pass

        def debug_code(self, code, language):
            calls["args"] = (code, language)
            return {"text": "fixed"}

    monkeypatch.setattr(service, "CodeExecutionCoder", FakeCoder)
    result = service.debug_code(str(f), "k", "claude-sonnet-5")
    assert result["text"] == "fixed"
    assert calls["args"] == ("print('oops'", "py")


# ── Hooks ────────────────────────────────────────────────────────────────

def test_hooks_add_list_remove_roundtrip(monkeypatch, tmp_path):
    import infrastructure.local_storage.hooks_permissions_store as store
    monkeypatch.setattr(store, "HOOKS_FILE", tmp_path / "hooks.json")

    service.hooks_add("pre_tool_use", "echo hi", tool_match="Bash")
    hooks = service.hooks_list()
    assert len(hooks) == 1
    assert hooks[0].event == HookEvent.PRE_TOOL_USE
    assert hooks[0].command == "echo hi"

    assert service.hooks_remove(0) is True
    assert service.hooks_list() == []


# ── Permissions ──────────────────────────────────────────────────────────

def test_perms_add_and_list(monkeypatch, tmp_path):
    import infrastructure.local_storage.hooks_permissions_store as store
    monkeypatch.setattr(store, "PERMS_FILE", tmp_path / "perms.json")

    service.perms_add("run_shell", "deny", "too risky")
    rules = service.perms_list()
    assert rules[0].pattern == "run_shell"
    assert rules[0].decision == Decision.DENY


# ── Plan Mode ────────────────────────────────────────────────────────────

def test_plan_propose_delegates(monkeypatch):
    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def propose(self, task, context=""):
            return Plan(task=task, steps=[PlanStep(number=1, description="do it")])

    monkeypatch.setattr(service, "PlanModeAgent", FakeAgent)
    plan = service.plan_propose("build a thing", "k", "claude-sonnet-5")
    assert plan.task == "build a thing"
    assert len(plan.steps) == 1


def test_plan_execute_all_fires_callbacks_in_order(monkeypatch):
    order = []

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def execute_step(self, plan, number):
            step = next(s for s in plan.steps if s.number == number)
            order.append(f"exec:{number}")
            step.completed = True
            step.result = "ok"
            return step

        @staticmethod
        def approve(plan):
            plan.approved = True
            return plan

    monkeypatch.setattr(service, "PlanModeAgent", FakeAgent)
    plan = Plan(task="t", steps=[PlanStep(number=1, description="a"), PlanStep(number=2, description="b")])

    service.plan_execute_all(
        plan, "k", "claude-sonnet-5",
        on_step_start=lambda s: order.append(f"start:{s.number}"),
        on_step=lambda s: order.append(f"done:{s.number}"),
    )
    assert order == ["start:1", "exec:1", "done:1", "start:2", "exec:2", "done:2"]
    assert plan.approved is True


# ── Multi-Agent Router ───────────────────────────────────────────────────

def test_route_query_merges_extra_table(monkeypatch):
    captured = {}

    def fake_route_and_call(prompt, api_key, model, table, explain=False, parallel=False, on_route=None):
        captured["table"] = table
        return "answer"

    monkeypatch.setattr(service, "route_and_call", fake_route_and_call)
    result = service.route_query("q", "k", "claude-sonnet-5", extra_table={"custom": "does custom things"})
    assert result == "answer"
    assert captured["table"]["custom"] == "does custom things"
    assert "code" in captured["table"]  # defaults still present


def test_route_list_table_merges_without_calling_api():
    table = service.route_list_table({"custom": "desc"})
    assert table["custom"] == "desc"
    assert "code" in table

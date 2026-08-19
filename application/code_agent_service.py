"""
application/code_agent_service.py — Use-case layer for Agent Execution &
Code (partial — Code Execution tool, Hooks, Permissions, Plan Mode,
Multi-Agent Router; claude_code.py's CodeAgent/sessions/MCP/subagents/
skills/todos are not yet migrated, see exec-planing.md Phase C)
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Same pattern as tools_service.py / messaging_service.py: plain functions,
no print(), no argparse.
"""

from typing import Callable, Optional

from infrastructure.anthropic_api.code_agent_gateway import (
    CodeExecutionCoder, PlanModeAgent, route_and_call,
)
from infrastructure.local_storage.hooks_permissions_store import HookManager, PermissionEngine
from domain.agent_execution import HookEvent, Decision, DEFAULT_ROUTING_TABLE, Plan

_NOOP = lambda *a, **k: None  # noqa: E731


# ── Code Execution tool ──────────────────────────────────────────────────

def run_code_exec(prompt: str, api_key: str, model: str, file_ids: Optional[list] = None,
                   output_dir: Optional[str] = None,
                   code_exec_version: str = "code_execution_20260521",
                   on_file_saved: Callable[[str], None] = _NOOP) -> dict:
    cec = CodeExecutionCoder(api_key=api_key, model=model, code_exec_version=code_exec_version)
    return cec.execute(prompt, file_ids=file_ids, output_dir=output_dir, on_file_saved=on_file_saved)


def debug_code(file_path: str, api_key: str, model: str,
                code_exec_version: str = "code_execution_20260521") -> dict:
    from pathlib import Path
    code = Path(file_path).read_text()
    lang = Path(file_path).suffix.lstrip(".") or "python"
    cec = CodeExecutionCoder(api_key=api_key, model=model, code_exec_version=code_exec_version)
    return cec.debug_code(code, lang)


# ── Hooks ────────────────────────────────────────────────────────────────

def hooks_add(event: str, command: str, tool_match: Optional[str] = None):
    hm = HookManager()
    hm.add(HookEvent(event), command, tool_match)


def hooks_list() -> list:
    return HookManager().hooks


def hooks_remove(idx: int) -> bool:
    return HookManager().remove(idx)


# ── Permissions ──────────────────────────────────────────────────────────

def perms_list() -> list:
    return PermissionEngine().rules


def perms_add(pattern: str, decision: str, reason: str = ""):
    PermissionEngine().add(pattern, Decision(decision), reason)


# ── Plan Mode ────────────────────────────────────────────────────────────

def plan_propose(task: str, api_key: str, model: str, context: str = "") -> Plan:
    agent = PlanModeAgent(api_key, model)
    return agent.propose(task, context)


def plan_execute_all(plan: Plan, api_key: str, model: str,
                      on_step_start: Callable = _NOOP,
                      on_step: Callable = _NOOP) -> Plan:
    agent = PlanModeAgent(api_key, model)
    PlanModeAgent.approve(plan)
    for s in plan.steps:
        if not s.completed:
            on_step_start(s)
            agent.execute_step(plan, s.number)
            on_step(s)
    return plan


# ── Multi-Agent Router ───────────────────────────────────────────────────

def route_query(prompt: str, api_key: str, model: str, explain: bool = False,
                 parallel: bool = False, extra_table: Optional[dict] = None,
                 on_route: Callable[[str, str], None] = _NOOP) -> str:
    table = dict(DEFAULT_ROUTING_TABLE)
    if extra_table:
        table.update(extra_table)
    return route_and_call(prompt, api_key, model, table, explain=explain,
                           parallel=parallel, on_route=on_route)


def route_list_table(extra_table: Optional[dict] = None) -> dict:
    table = dict(DEFAULT_ROUTING_TABLE)
    if extra_table:
        table.update(extra_table)
    return table

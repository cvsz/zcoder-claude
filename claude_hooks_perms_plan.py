"""
claude_hooks_perms_plan.py — Hooks, Permissions, Plan Mode (compatibility shim)
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - HookEvent, Hook, HookResult, Decision, PermRule, DEFAULT_RULES,
    PlanStep, Plan → domain/agent_execution.py
  - HookManager, PermissionEngine → infrastructure/local_storage/hooks_permissions_store.py
  - PlanModeAgent → infrastructure/anthropic_api/code_agent_gateway.py
  - cmd_hooks_add, cmd_hooks_list, cmd_hooks_remove, cmd_perms_list,
    cmd_perms_add, cmd_plan → interfaces/cli/commands/code_agent_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.agent_execution import (
    HookEvent, Hook, HookResult, Decision, PermRule, DEFAULT_RULES, PlanStep, Plan,
)
from infrastructure.local_storage.hooks_permissions_store import HookManager, PermissionEngine
from infrastructure.anthropic_api.code_agent_gateway import PlanModeAgent
from interfaces.cli.commands.code_agent_commands import (
    cmd_hooks_add, cmd_hooks_list, cmd_hooks_remove,
    cmd_perms_list, cmd_perms_add, cmd_plan,
)

__all__ = [
    "HookEvent", "Hook", "HookResult", "HookManager",
    "Decision", "PermRule", "DEFAULT_RULES", "PermissionEngine",
    "PlanStep", "Plan", "PlanModeAgent",
    "cmd_hooks_add", "cmd_hooks_list", "cmd_hooks_remove",
    "cmd_perms_list", "cmd_perms_add", "cmd_plan",
]

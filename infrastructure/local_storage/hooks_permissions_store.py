"""
infrastructure/local_storage/hooks_permissions_store.py — local-disk
persistence and subprocess execution for Hooks and Permissions
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_hooks_perms_plan.py's HookManager and
PermissionEngine. HookManager runs hook commands via subprocess — real
local process execution, not an HTTP call, so it lives here rather than
in infrastructure/anthropic_api/ alongside code_agent_gateway.py (which
holds that module's Plan Mode third instead, since Plan Mode is a pure
Anthropic API caller with no local state).
"""

import json
import os
import subprocess
from pathlib import Path

from domain.agent_execution import (
    DEFAULT_RULES,
    Decision,
    Hook,
    HookEvent,
    HookResult,
    PermRule,
    evaluate_perm,
    hook_matches,
)

HOOKS_FILE = Path.home() / ".zcoder" / "hooks.json"
PERMS_FILE = Path.home() / ".zcoder" / "permissions.json"


class HookManager:
    def __init__(self):
        self.hooks: list[Hook] = []
        self._load()

    def _load(self):
        if HOOKS_FILE.exists():
            try:
                self.hooks = [Hook.from_dict(d) for d in json.loads(HOOKS_FILE.read_text())]
            except Exception:
                pass

    def save(self):
        HOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        HOOKS_FILE.write_text(json.dumps([h.to_dict() for h in self.hooks], indent=2))

    def add(self, event: HookEvent, command: str, tool_match: str | None = None, description: str = ""):
        self.hooks.append(Hook(event=event, command=command, tool_match=tool_match, description=description))
        self.save()

    def remove(self, idx: int) -> bool:
        if 0 <= idx < len(self.hooks):
            del self.hooks[idx]
            self.save()
            return True
        return False

    def fire(self, event: HookEvent, tool_name: str | None = None) -> list[HookResult]:
        env = {**os.environ}
        if tool_name:
            env["ZCODER_TOOL_NAME"] = tool_name
        env["ZCODER_HOOK_EVENT"] = event.value
        results = []
        for h in [h for h in self.hooks if hook_matches(h, event, tool_name)]:
            try:
                p = subprocess.run(h.command, shell=True, capture_output=True, text=True, timeout=30, env=env)
                blocked = event == HookEvent.PRE_TOOL_USE and p.returncode != 0
                results.append(
                    HookResult(
                        hook=h, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr, blocked=blocked
                    )
                )
            except subprocess.TimeoutExpired:
                results.append(
                    HookResult(
                        hook=h,
                        returncode=-1,
                        stdout="",
                        stderr="timeout",
                        blocked=(event == HookEvent.PRE_TOOL_USE),
                    )
                )
        return results

    def guarded_call(self, tool_name: str, fn, *args, **kwargs):
        pre = self.fire(HookEvent.PRE_TOOL_USE, tool_name)
        blocked = [r for r in pre if r.blocked]
        if blocked:
            reasons = "; ".join(r.stderr.strip() or r.hook.command for r in blocked)
            raise PermissionError(f"Tool '{tool_name}' blocked by hook: {reasons}")
        result = fn(*args, **kwargs)
        self.fire(HookEvent.POST_TOOL_USE, tool_name)
        return result


class PermissionEngine:
    def __init__(self):
        self.rules: list[PermRule] = []
        self._load()

    def _load(self):
        if PERMS_FILE.exists():
            try:
                self.rules = [PermRule.from_dict(d) for d in json.loads(PERMS_FILE.read_text())]
            except Exception:
                self.rules = list(DEFAULT_RULES)
        else:
            self.rules = list(DEFAULT_RULES)

    def save(self):
        PERMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERMS_FILE.write_text(json.dumps([r.to_dict() for r in self.rules], indent=2))

    def add(self, pattern: str, decision: Decision, reason: str = ""):
        self.rules.insert(0, PermRule(pattern=pattern, decision=decision, reason=reason))
        self.save()

    def evaluate(self, tool_name: str) -> PermRule:
        return evaluate_perm(tool_name, self.rules)

    def is_allowed(self, tool_name: str, ask_cb=None) -> bool:
        r = self.evaluate(tool_name)
        if r.decision == Decision.ALLOW:
            return True
        if r.decision == Decision.DENY:
            return False
        return bool(ask_cb(r, tool_name)) if ask_cb else False

"""
domain/agent_execution.py — Agent Execution & Code bounded context: pure
data + logic (partial — covers claude_hooks_perms_plan.py,
claude_sandbox.py, claude_router.py; claude_code.py's 9 classes are not
yet migrated, see the shim docstring there and exec-planing.md Phase C)
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Domain layer: zero I/O, zero print(), zero HTTP. Extracted 2026-08-16.
"""

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

# ── Hooks (claude_hooks_perms_plan.py) ──────────────────────────────────────

class HookEvent(Enum):
    PRE_TOOL_USE  = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    SESSION_START = "session_start"
    SESSION_END   = "session_end"


@dataclass
class Hook:
    event:       HookEvent
    command:     str
    tool_match:  Optional[str] = None
    description: str = ""

    def to_dict(self):
        return {"event": self.event.value, "command": self.command,
                "tool_match": self.tool_match, "description": self.description}

    @staticmethod
    def from_dict(d):
        return Hook(event=HookEvent(d["event"]), command=d["command"],
                    tool_match=d.get("tool_match"), description=d.get("description", ""))


@dataclass
class HookResult:
    hook:       Hook
    returncode: int
    stdout:     str
    stderr:     str
    blocked:    bool = False


def hook_matches(hook: Hook, event: HookEvent, tool_name: Optional[str]) -> bool:
    """Pure filter: does `hook` fire for this event/tool_name pair? Split
    out of HookManager.fire()'s inline filtering (which also does the
    subprocess call — that stays in the infrastructure adapter) so the
    matching rule itself is unit-testable without a subprocess."""
    if hook.event != event:
        return False
    if hook.tool_match and tool_name and hook.tool_match not in tool_name:
        return False
    return True


# ── Permissions (claude_hooks_perms_plan.py) ────────────────────────────────

class Decision(Enum):
    ALLOW = "allow"
    DENY  = "deny"
    ASK   = "ask"


@dataclass
class PermRule:
    pattern:  str
    decision: Decision
    reason:   str = ""

    def to_dict(self):
        return {"pattern": self.pattern, "decision": self.decision.value, "reason": self.reason}

    @staticmethod
    def from_dict(d):
        return PermRule(pattern=d["pattern"], decision=Decision(d["decision"]), reason=d.get("reason", ""))


DEFAULT_RULES = [
    PermRule("read_*",     Decision.ALLOW, "Read-only"),
    PermRule("list_*",     Decision.ALLOW, "Listing is safe"),
    PermRule("git_status", Decision.ALLOW, "Read-only git"),
    PermRule("git_diff",   Decision.ALLOW, "Read-only git"),
    PermRule("delete_*",   Decision.ASK,   "Destructive"),
    PermRule("run_shell",  Decision.ASK,   "Arbitrary execution"),
    PermRule("git_push",   Decision.ASK,   "Publishes changes"),
]


def evaluate_perm(tool_name: str, rules: List[PermRule]) -> PermRule:
    """Pure rule matching (fnmatch), split out of PermissionEngine.evaluate()
    so the fallback-to-ASK matching logic is unit-testable without a
    filesystem-backed rule list."""
    import fnmatch
    for r in rules:
        if fnmatch.fnmatch(tool_name, r.pattern):
            return r
    return PermRule("*", Decision.ASK, "No matching rule")


# ── Plan Mode data shapes (claude_hooks_perms_plan.py) ──────────────────────

@dataclass
class PlanStep:
    number:      int
    description: str
    result:      Optional[str] = None
    completed:   bool = False


@dataclass
class Plan:
    task:     str
    steps:    List[PlanStep]
    approved: bool = False

    def to_markdown(self) -> str:
        lines = [f"# Plan: {self.task}", ""]
        for s in self.steps:
            mark = "x" if s.completed else " "
            lines.append(f"- [{mark}] {s.number}. {s.description}")
        return "\n".join(lines)


# ── Sandboxed Bash policy (claude_sandbox.py) ───────────────────────────────
# Models Claude Code's sandboxed Bash tool: OS-level-style filesystem and
# network isolation enforced around shell commands the agent runs. This is
# a best-effort, portable sandbox (no kernel namespaces) — see the
# original module's docstring (preserved in the shim) for the full
# defense-in-depth caveat.

NETWORK_BINARIES = {
    "curl", "wget", "nc", "ncat", "netcat", "ssh", "scp", "sftp", "rsync",
    "telnet", "ftp", "http", "https", "wormhole", "ngrok",
}
NETWORK_PIP_NPM_FLAGS = {
    "pip": {"install", "download"},
    "pip3": {"install", "download"},
    "npm": {"install", "i", "ci", "update", "publish"},
    "npx": set(),
    "yarn": {"add", "install", "upgrade"},
    "git": {"clone", "fetch", "pull", "push"},
}


class SandboxViolation(Exception):
    pass


def tokenize_command(command: str) -> list:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def check_network(command: str) -> Optional[str]:
    """Return a violation message if the command looks like a network call, else None."""
    tokens = tokenize_command(command)
    if not tokens:
        return None
    for i, tok in enumerate(tokens):
        base = Path(tok).name
        if base in NETWORK_BINARIES:
            return (f"network binary '{base}' is blocked inside the sandbox "
                     "(run with --code-agent-sandbox-allow-net to permit)")
        if base in NETWORK_PIP_NPM_FLAGS:
            sub_flags = NETWORK_PIP_NPM_FLAGS[base]
            rest = set(tokens[i + 1:i + 2])
            if not sub_flags or rest & sub_flags:
                return f"'{base}' network operation is blocked inside the sandbox"
        if base == "python" or base == "python3":
            joined = " ".join(tokens[i:i + 3])
            if "http.server" in joined or "urllib" in joined:
                return "python network access is blocked inside the sandbox"
    if re.search(r"https?://|ftp://|ssh://", command):
        return "command contains a network URL, blocked inside the sandbox"
    return None


def check_filesystem(command: str, allowed_roots: list) -> Optional[str]:
    """Best-effort static check: flag absolute paths or '..' traversal
    outside the allowed roots when they appear as redirection targets or
    common mutation-command arguments. Not a full parser — defense in
    depth only."""
    allowed = [Path(r).resolve() for r in allowed_roots]

    def _is_allowed(p: str) -> bool:
        try:
            resolved = Path(p).expanduser().resolve()
        except Exception:
            return True
        return any(resolved == root or root in resolved.parents for root in allowed)

    for m in re.finditer(r"(?:>>?)\s*([^\s|&;]+)", command):
        target = m.group(1)
        if (target.startswith("/") or target.startswith("~")) and not _is_allowed(target):
            return f"redirect target '{target}' is outside the sandbox root(s)"

    for m in re.finditer(r"\b(rm|mv|cp)\b[^|;&]*", command):
        for path_tok in re.findall(r"(?:^|\s)(/[^\s]+|~[^\s]*)", m.group(0)):
            if not _is_allowed(path_tok):
                return f"'{m.group(1)}' targets '{path_tok}' outside the sandbox root(s)"
    return None


def enforce(command: str, cwd: str, allow_net: bool = False,
            extra_roots: Optional[list] = None) -> None:
    """Raise SandboxViolation if the command violates sandbox policy."""
    roots = [cwd] + (extra_roots or [])
    if not allow_net:
        violation = check_network(command)
        if violation:
            raise SandboxViolation(violation)
    violation = check_filesystem(command, roots)
    if violation:
        raise SandboxViolation(violation)


# ── Multi-Agent Router table (claude_router.py) ─────────────────────────────

DEFAULT_ROUTING_TABLE = {
    "code":       "Write, review, refactor, debug, or explain code in any language",
    "research":   "Deep factual research, literature review, or evidence synthesis",
    "write":      "Long-form writing, editing, summarisation, translation, or copywriting",
    "analyse":    "Data analysis, statistical interpretation, or business insight extraction",
    "plan":       "Project planning, task breakdown, roadmaps, or strategy",
    "brainstorm": "Idea generation, creative thinking, or blue-sky exploration",
    "security":   "Security review, threat modelling, CVE analysis, or hardening advice",
    "architect":  "System design, architecture decisions, or technology selection",
    "debug":      "Root-cause analysis and bug fixing for code or systems",
    "automate":   "Workflow automation, scripting, CI/CD, or DevOps pipeline design",
}

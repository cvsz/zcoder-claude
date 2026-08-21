"""
# mypy: ignore-errors
application/code_agent_loop_service.py — Use-case layer for Claude Code
/ Agent SDK (sessions, hooks, MCP, subagents, skills, todos, memory, the
main agentic query loop)
AI Model Coder CLI v1.49.0 (Clean Architecture refactor, Phase C)

Same pattern as the rest of this migration: plain functions, no
print()/input(), no argparse. Orchestrates
infrastructure/anthropic_api/code_agent_loop_gateway.py (the HTTP-calling
CodeAgent) and infrastructure/local_storage/code_agent_store.py (every
local-disk-backed class in this context).
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

from domain.code_agent import AGENTS_DIR, MCP_JSON, SESSIONS_DIR, SETTINGS_JSON, SKILLS_DIR, USER_MEMORY
from domain.tools import build_context_management
from infrastructure.anthropic_api.code_agent_loop_gateway import (
    CodeAgent,
    default_can_use_tool,
)
from infrastructure.local_storage.code_agent_store import (
    CodeSession,
    HooksEngine,
    McpConnector,
    MemoryManager,
    SkillsRegistry,
    SubagentRegistry,
    TodoManager,
)

_NOOP = lambda *a, **k: None  # noqa: E731


# ── Session lifecycle ────────────────────────────────────────────────────


def load_or_create_session(
    session_id: str | None, cwd: str, model: str, permission: str, system: str | None
) -> tuple:
    """Returns (session, resumed: bool)."""
    if session_id:
        try:
            return CodeSession.load(session_id), True
        except FileNotFoundError:
            return (
                CodeSession(
                    session_id=session_id,
                    cwd=cwd,
                    model=model,
                    permission_mode=permission,
                    system_prompt=system or "",
                ),
                False,
            )
    return CodeSession(cwd=cwd, model=model, permission_mode=permission, system_prompt=system or ""), False


def apply_output_style(session: CodeSession, output_style: str):
    try:
        from claude_output_styles import system_prompt_fragment

        fragment = system_prompt_fragment(output_style)
        if fragment:
            session.system_prompt = (session.system_prompt + "\n\n" + fragment).strip()
    except ImportError:
        pass


def build_hooks_engine(hooks_file: str | None, on_warning: Callable[[str], None] = _NOOP) -> HooksEngine:
    engine = (
        HooksEngine.from_file(hooks_file, on_warning=on_warning)
        if hooks_file
        else HooksEngine.from_settings()
    )
    return HooksEngine.with_plugins(engine)


def enable_sandbox(cwd: str, allow_net: bool, extra_roots: list | None = None):
    os.environ["AI_CODER_SANDBOX"] = "1"
    os.environ["AI_CODER_SANDBOX_NET"] = "1" if allow_net else "0"
    os.environ["AI_CODER_SANDBOX_ROOTS"] = json.dumps([str(Path(cwd).resolve())] + (extra_roots or []))


def add_plugin_bin_paths():
    try:
        from claude_plugins import plugin_bin_paths

        extra_bins = plugin_bin_paths()
        if extra_bins:
            os.environ["PATH"] = os.pathsep.join(extra_bins) + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass


def build_agent_context_editing(enabled: bool) -> dict | None:
    return build_context_management(clear_tool_uses=True) if enabled else None


def run_agent_query(
    agent: CodeAgent,
    prompt: str,
    session: CodeSession,
    tools: str,
    permission: str,
    hooks: HooksEngine,
    output_mode: str,
    context_management: dict | None,
    can_use_tool=default_can_use_tool,
    **callbacks,
) -> str:
    return agent.query(
        prompt=prompt,
        session=session,
        tools=tools,
        permission=permission,
        hooks=hooks,
        output_mode=output_mode,
        context_management=context_management,
        can_use_tool=can_use_tool,
        **callbacks,
    )


def run_subagent(task: str, api_key: str, model: str, cwd: str = ".", **callbacks) -> str:
    session = CodeSession(
        cwd=cwd,
        model=model,
        permission_mode="acceptEdits",
        system_prompt=(
            "You are a focused subagent. Complete ONLY the specific task. "
            "Be thorough. Return just the result."
        ),
    )
    agent = CodeAgent(api_key=api_key, model=model)
    return agent.query(
        task, session, tools="safe", permission="acceptEdits", output_mode="stream", **callbacks
    )


def generate_todos(prompt: str, api_key: str, model: str) -> tuple:
    """Ask Claude to decompose prompt into todos and add them to
    TodoManager. Returns (items, raw_on_error): on success `items` is
    the list of added todo dicts and `raw_on_error` is None; if the
    response couldn't be parsed as JSON, `items` is [] and
    `raw_on_error` is the raw response text — matching the original's
    two distinct outcomes (print each added item, or print the raw
    text on a parse exception). A regex miss with no exception (no
    `[...]` found in the response at all) also returns ([], None),
    same as the original silently printing nothing in that case."""
    tm = TodoManager()
    session = CodeSession(model=model, permission_mode="dontAsk")
    agent = CodeAgent(api_key=api_key, model=model)
    raw = agent.query(
        f"Break this task into 5-8 concrete todo items (JSON array of strings):\n{prompt}",
        session,
        tools="none",
        permission="dontAsk",
        output_mode="text",
    )
    try:
        import re

        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        if m:
            items = json.loads(m.group(0))
            return [tm.add(str(item)) for item in items], None
    except Exception:
        return [], raw
    return [], None


# ── Slash commands ───────────────────────────────────────────────────────


def mcp_server_list() -> list:
    return McpConnector.from_json_file().list_servers()


def subagent_list() -> list:
    reg = SubagentRegistry()
    reg.load()
    return reg.list()


def skills_list() -> list:
    reg = SkillsRegistry()
    reg.load()
    return reg.list()


def memory_combined() -> str:
    return MemoryManager().combined()


def find_custom_command(cmd: str) -> dict | None:
    """Returns {"content": str, "source": "custom"|"plugin", "name": str}
    or None if no matching command file/plugin command exists."""
    for d in (Path(".claude/commands"), SKILLS_DIR):
        if d.exists():
            for f in d.rglob("*.md"):
                if f.stem == cmd:
                    return {"content": f.read_text(), "source": "custom", "name": cmd}
    try:
        from claude_plugins import load_plugin_commands

        for entry in load_plugin_commands():
            if entry["name"] == cmd or entry["name"].split(":", 1)[-1] == cmd:
                return {"content": Path(entry["path"]).read_text(), "source": "plugin", "name": entry["name"]}
    except ImportError:
        pass
    return None


def run_custom_command(content: str, prompt: str, api_key: str, model: str, cwd: str, **callbacks):
    session = CodeSession(cwd=cwd, model=model)
    agent = CodeAgent(api_key=api_key, model=model)
    return agent.query(
        f"{content}\n\n{prompt}" if prompt else content,
        session,
        tools="code",
        permission="acceptEdits",
        **callbacks,
    )


# ── Cost / session listing ───────────────────────────────────────────────


def list_session_files(limit: int = 20) -> list:
    """Returns parsed session dicts, most recent last, best-effort (skips
    unparseable files)."""
    rows = []
    for sf in sorted(SESSIONS_DIR.glob("*.json"))[-limit:]:
        try:
            rows.append(json.loads(sf.read_text()))
        except Exception:
            pass
    return rows


# ── Doctor diagnostics ───────────────────────────────────────────────────


def run_diagnostics() -> list:
    """Returns [(check_name, ok: bool), ...]."""
    from domain.code_agent import MEMORY_FILE

    checks = [
        ("ANTHROPIC_API_KEY set", bool(os.getenv("ANTHROPIC_API_KEY"))),
        (".mcp.json exists", MCP_JSON.exists()),
        (".claude/settings.json", SETTINGS_JSON.exists()),
        (".claude/agents/ exists", AGENTS_DIR.exists()),
        (".claude/skills/ exists", SKILLS_DIR.exists()),
        ("CLAUDE.md exists", MEMORY_FILE.exists() or Path("CLAUDE.md").exists()),
        ("~/.claude/CLAUDE.md", USER_MEMORY.exists()),
        ("Sessions dir", SESSIONS_DIR.exists()),
    ]
    try:
        from claude_plugins import marketplace_list, plugin_list

        checks.append(("Plugins installed", len(plugin_list()) > 0))
        checks.append(("Marketplaces registered", len(marketplace_list()) > 0))
    except ImportError:
        pass
    return checks

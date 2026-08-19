"""
interfaces/cli/commands/code_agent_loop_commands.py — CLI presentation
for the Claude Code / Agent SDK agentic loop (sessions, MCP, subagents,
skills, todos, slash commands, cost/session listing, doctor)
AI Model Coder CLI v1.49.0 (Clean Architecture refactor, Phase C)

Only print()/input() live here — all real work is delegated to
application/code_agent_loop_service.py. Extracted 2026-08-17 from
claude_code.py's cmd_code_agent, cmd_code_subagent, cmd_code_todo,
cmd_code_slash, cmd_code_cost, cmd_code_list_sessions,
cmd_code_list_tools, _run_doctor.

Permission-prompt reproduction: the original's non-interactive fallback
(no can_use_tool callback supplied) printed a yellow "[permission] ..."
line and blocked on input("Approve? [Y/n]") for every non-read-only
tool, silently auto-approving read-only tools. That behavior now lives
in _on_permission_prompt (the print) + _interactive_can_use_tool (the
input()), passed as this module's default callbacks to
service.run_agent_query — see
infrastructure/anthropic_api/code_agent_loop_gateway.py's module
docstring for why the gateway itself no longer special-cases "no
callback supplied".  One deliberate, minor behavior change: the
original distinguished an explicit "n" answer ("[DENIED by user]") from
no terminal being attached ("[DENIED — no terminal]"); the gateway's
can_use_tool callback returns a plain bool now, so both cases surface
as "[DENIED by user]" — the tool is still correctly blocked either way,
only the denial message's wording is unified.
"""

import json
from pathlib import Path

from application import code_agent_loop_service as service
from domain.code_agent import (
    BUILTIN_SLASH_COMMANDS, SLASH_COMMAND_ALIASES, READ_ONLY_TOOLS,
    TOOL_PRESETS, PERMISSION_MODES, COMMANDS_DIR, SKILLS_DIR,
)
from infrastructure.anthropic_api.code_agent_loop_gateway import CodeAgent
from infrastructure.local_storage.code_agent_store import (
    McpConnector, SubagentRegistry, SkillsRegistry,
)

__all__ = [
    "cmd_code_agent", "cmd_code_subagent", "cmd_code_todo", "cmd_code_slash",
    "cmd_code_cost", "cmd_code_list_sessions", "cmd_code_list_tools",
]


# ── shared warning/permission printers ──────────────────────────────────

def _warn(msg: str):
    """Plain '[WARN] ...' line — matches HooksEngine.from_file's,
    McpConnector.from_json_file's, and SubagentRegistry._load_one's
    original uncolored print()."""
    print(f"  [WARN] {msg}")


def _hook_fire_warning(msg: str):
    """HooksEngine.fire() funnels 3 distinct original print() call
    sites (exit-1 warning, timeout, exception) through one on_warning
    callback — recover the original's color choice (yellow for a
    handler's own non-blocking warning, red for timeout/error) from the
    message text, since that's all that crosses the callback boundary."""
    if msg.endswith("timed out") or "] error:" in msg:
        print(f"  \033[91m{msg}\033[0m")
    else:
        print(f"  \033[93m{msg}\033[0m")


def _on_permission_prompt(name: str, inputs: dict):
    if name not in READ_ONLY_TOOLS:
        print(f"\n\033[93m  [permission] {name}({json.dumps(inputs)[:60]})\033[0m")


def _interactive_can_use_tool(name: str, inputs: dict) -> bool:
    if name in READ_ONLY_TOOLS:
        return True
    try:
        ans = input("  Approve? [Y/n] ").strip().lower()
        return ans != "n"
    except (EOFError, KeyboardInterrupt):
        return False


# ── --code-agent ─────────────────────────────────────────────────────────

def cmd_code_agent(
    prompt: str, api_key: str, model: str,
    cwd: str = ".", tools: str = "all",
    permission: str = "askPermission",
    session_id: str = None, system: str = None,
    mcp_urls: list = None, output_mode: str = "stream",
    hooks_file: str = None, checkpoint: bool = False,
    output_file: str = None,
    output_style: str = None,
    sandbox: bool = False, sandbox_allow_net: bool = False,
    sandbox_roots: list = None,
    headless: bool = False,
    agent_context_editing: bool = False,
):
    """Main --code-agent entry point.

    agent_context_editing: opt-in context editing (clear_tool_uses) for this
    agent loop, on top of the existing Compaction support — the two are
    complementary (clearing drops stale tool results; Compaction summarizes
    the whole conversation), so this is safe to combine with an already
    long-running session. See --agent-context-editing.
    """
    if not headless:
        print(f"\033[94mℹ Claude Code Agent | tools={tools} | permission={permission}\033[0m")
        print(f"  cwd: {Path(cwd).resolve()}\n")

    session, resumed = service.load_or_create_session(session_id, cwd, model, permission, system)
    if resumed and not headless:
        print(f"\033[90m  Resumed session: {session.id} ({len(session.turns)} turns)\033[0m\n")

    if output_style:
        service.apply_output_style(session, output_style)

    # MCP (project .mcp.json + plugin-bundled servers + ad-hoc --code-agent-mcp URLs)
    mcp = McpConnector.from_json_file(on_warning=_warn)
    for url in (mcp_urls or []):
        mcp.add_from_url(url)

    # Hooks: project/global settings hooks, merged with plugin-bundled hooks
    hooks_engine = service.build_hooks_engine(hooks_file, on_warning=_warn)

    # Sandboxed Bash: wrap permission/tool execution with filesystem+network checks
    if sandbox:
        service.enable_sandbox(cwd, sandbox_allow_net, sandbox_roots)
        if not headless:
            net_state = "network allowed" if sandbox_allow_net else "network blocked"
            print(f"\033[93m  ⚙ Sandbox enabled ({net_state})\033[0m")

    # Plugin bin/ dirs onto PATH for the duration of this run
    service.add_plugin_bin_paths()

    # Skills / Agents (plugin-aware via their own .load())
    skills = SkillsRegistry(); skills.load()
    agents = SubagentRegistry(); agents.load(on_warning=_warn)

    # Checkpoint before run
    if checkpoint:
        cp = session.checkpoint(f"before: {prompt[:40]}")
        if not headless:
            print(f"  \033[90m✓ Checkpoint: {cp['id']}\033[0m")

    # Headless/print mode forces non-interactive, non-streaming text output —
    # suitable for piping into other tools or scripts (matches `claude -p`).
    effective_output_mode = "text" if headless else output_mode

    # Context editing (opt-in): reuses domain.tools.build_context_management
    # rather than duplicating it.
    cm = service.build_agent_context_editing(agent_context_editing)
    if agent_context_editing and not headless:
        print("\033[90m  ⚙ Context editing enabled (clear_tool_uses)\033[0m")

    # Run
    agent = CodeAgent(api_key=api_key, model=model)
    result = service.run_agent_query(
        agent, prompt, session, tools, permission, hooks_engine,
        effective_output_mode, cm,
        can_use_tool=_interactive_can_use_tool,
        on_turn_start=lambda n: print(f"\033[90m[turn {n}]\033[0m ", end="", flush=True),
        on_text=lambda text: print(text),
        on_tool_call=lambda name, tinput: print(
            f"  \033[90m→ {name}({json.dumps(tinput)[:60]})\033[0m"),
        on_permission_prompt=_on_permission_prompt,
        on_warning=_hook_fire_warning,
    )

    if effective_output_mode != "stream":
        print(result)

    if output_file:
        Path(output_file).write_text(result)
        if not headless:
            print(f"\033[92m✓ Saved to {output_file}\033[0m")

    if not headless:
        print(f"\n\033[90m{session.cost_summary()}\033[0m")
        print(f"\033[90m  Resume: ai-coder --code-agent-session {session.id} -p \"...\"\033[0m")
    return result


# ── --code-agent-subagent ────────────────────────────────────────────────

def cmd_code_subagent(task: str, api_key: str, model: str, cwd: str = "."):
    """Spawn a focused subagent for a sub-task."""
    print("\033[94mℹ Spawning subagent…\033[0m\n")
    result = service.run_subagent(
        task, api_key, model, cwd=cwd,
        on_turn_start=lambda n: print(f"\033[90m[turn {n}]\033[0m ", end="", flush=True),
        on_text=lambda text: print(text),
        on_tool_call=lambda name, tinput: print(
            f"  \033[90m→ {name}({json.dumps(tinput)[:60]})\033[0m"),
        on_warning=_hook_fire_warning,
    )
    return result


# ── --code-agent-todo ─────────────────────────────────────────────────────

def cmd_code_todo(prompt: str, api_key: str, model: str):
    """Generate and manage a todo list from a prompt."""
    print(f"\033[94mℹ Todo list from: {prompt[:60]}\033[0m\n")
    items, raw_on_error = service.generate_todos(prompt, api_key, model)
    if raw_on_error is not None:
        print(raw_on_error)
    else:
        for t in items:
            print(f"  ○ [{t['id']}] {t['text']}")


# ── --code-agent-slash ────────────────────────────────────────────────────

def cmd_code_slash(command: str, api_key: str, model: str,
                    cwd: str = ".", prompt: str = ""):
    """Handle slash commands."""
    cmd = command.lstrip("/").lower()
    full_cmd = SLASH_COMMAND_ALIASES.get(cmd, f"/{cmd}")

    if cmd == "clear":
        print("\033[92m✓ Session cleared.\033[0m")
        return

    if cmd == "compact":
        print("\033[94mℹ Compacting message history (summarising)…\033[0m")
        # Stub: in real SDK this compacts via PreCompact hook
        return

    if cmd in ("help", "?"):
        print("\nBuilt-in slash commands:")
        for name, desc in BUILTIN_SLASH_COMMANDS.items():
            print(f"  {name:<15} — {desc}")
        for d in (COMMANDS_DIR, SKILLS_DIR):
            if d.exists():
                for f in d.rglob("*.md"):
                    print(f"  /{f.stem:<13} — custom command from {f.relative_to(d)}")
        return

    if cmd == "cost":
        print("Session cost tracking (use --code-agent-cost for full summary)")
        return

    if cmd in ("status", "model", "mcp", "agents", "skills", "memory", "doctor",
               "plugin", "output-style", "statusline"):
        if cmd == "model":
            print(f"  Current model: {model}")
        elif cmd == "mcp":
            servers = service.mcp_server_list()
            if servers:
                for s in servers:
                    print(f"  {s['name']}: {s.get('type','?')} {s.get('url','')}")
            else:
                print("  No MCP servers configured. Add to .mcp.json")
        elif cmd == "agents":
            for a in service.subagent_list():
                tag = f" [{a['plugin']}]" if a.get("plugin") else ""
                print(f"  {a['name']}{tag}: {a['description']}")
        elif cmd == "skills":
            for s in service.skills_list():
                print(f"  {s['name']} ({s['source']}): {s['description']}")
        elif cmd == "memory":
            mem = service.memory_combined()
            print(mem if mem else "  No memory (CLAUDE.md) found.")
        elif cmd == "doctor":
            _run_doctor()
        elif cmd == "plugin":
            from claude_plugins import cmd_plugin_list
            cmd_plugin_list()
        elif cmd == "output-style":
            from claude_output_styles import cmd_list_output_styles
            cmd_list_output_styles()
        elif cmd == "statusline":
            from claude_settings import cmd_status_line
            cmd_status_line(model=model, cwd=cwd)
        return

    # Custom slash command (project/skills dirs, then plugins)
    found = service.find_custom_command(cmd)
    if found:
        label = full_cmd if found["source"] == "custom" else f"/{found['name']}"
        print(f"\033[94mℹ Running {'custom' if found['source']=='custom' else 'plugin'} "
              f"command: {label}\033[0m\n")
        service.run_custom_command(
            found["content"], prompt, api_key, model, cwd,
            on_turn_start=lambda n: print(f"\033[90m[turn {n}]\033[0m ", end="", flush=True),
            on_text=lambda text: print(text),
            on_tool_call=lambda name, tinput: print(
                f"  \033[90m→ {name}({json.dumps(tinput)[:60]})\033[0m"),
            on_warning=_hook_fire_warning,
        )
        return

    print(f"\033[91m✗ Unknown slash command: {full_cmd}\033[0m")
    print("  Run: ai-coder --code-agent-slash help")


# ── --code-agent-cost ─────────────────────────────────────────────────────

def cmd_code_cost(api_key: str):
    """Show cost summary across all sessions."""
    rows = service.list_session_files(limit=20)
    total_in, total_out, total_cost = 0, 0, 0.0
    print(f"\n{'SESSION':<18}{'TURNS':<8}{'IN':<12}{'OUT':<12}{'COST'}")
    print("─" * 60)
    for d in rows:
        try:
            i = d.get("input_tokens", 0)
            o = d.get("output_tokens", 0)
            c = d.get("cost_usd", 0.0)
            t = len(d.get("turns", [])) // 2
            total_in += i; total_out += o; total_cost += c
            print(f"{d['id'][:16]:<18}{t:<8}{i:,<12}{o:,<12}${c:.4f}")
        except Exception:
            pass
    print("─" * 60)
    print(f"{'TOTAL':<18}{'':8}{total_in:,<12}{total_out:,<12}${total_cost:.4f}")


# ── --code-agent-sessions ─────────────────────────────────────────────────

def cmd_code_list_sessions():
    rows = service.list_session_files(limit=25)
    if not rows:
        print("No code agent sessions saved.")
        return
    print(f"\n{'ID':<18}{'TURNS':<8}{'MODEL':<25}{'UPDATED'}")
    print("─" * 65)
    for d in rows:
        try:
            t = len(d.get("turns", [])) // 2
            print(f"{d['id'][:16]:<18}{t:<8}{d.get('model','')[:24]:<25}{d.get('updated_at','')[:10]}")
        except Exception:
            pass


# ── --code-agent-tools ────────────────────────────────────────────────────

def cmd_code_list_tools():
    print("\nBuilt-in tools:")
    descs = {
        "Read": "Read file contents",       "Write": "Write a file",
        "Edit": "Edit part of a file",      "MultiEdit": "Multi-location edit",
        "Bash": "Run bash commands",        "Glob": "Find files by pattern",
        "Grep": "Search file contents",     "LS": "List directory",
        "WebSearch": "Search the web",      "WebFetch": "Fetch a URL",
        "TodoRead": "Read todo list",       "TodoWrite": "Update todo list",
        "NotebookRead": "Read Jupyter nb",  "NotebookEdit": "Edit Jupyter nb",
        "Task": "Spawn a subagent task",
    }
    for name, desc in descs.items():
        print(f"  {name:<15} — {desc}")
    print("\nTool presets:")
    for name, preset_tools in TOOL_PRESETS.items():
        print(f"  {name:<12} — {', '.join(preset_tools[:5])}{'…' if len(preset_tools) > 5 else ''}")
    print("\nPermission modes:")
    for mode, desc in PERMISSION_MODES.items():
        print(f"  {mode:<20} — {desc}")


# ── doctor diagnostics ────────────────────────────────────────────────────

def _run_doctor():
    """Diagnostics for Claude Code environment."""
    print("\n\033[94mℹ Claude Code Diagnostics\033[0m")
    checks = service.run_diagnostics()
    all_ok = True
    for name, ok in checks:
        icon = "\033[92m✓\033[0m" if ok else "\033[93m○\033[0m"
        print(f"  {icon} {name}")
        if not ok:
            all_ok = False
    if all_ok:
        print("\n\033[92m✓ All checks passed.\033[0m")
    else:
        print("\n\033[93m⚠ Some items not configured (optional).\033[0m")

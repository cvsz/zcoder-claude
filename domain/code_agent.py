"""
domain/code_agent.py — Claude Code / Agent SDK bounded context: pure
data + pure logic
AI Model Coder CLI v1.49.0 (Clean Architecture refactor, Phase C)

Domain layer: zero I/O, zero print(), zero HTTP. Extracted 2026-08-17
from claude_code.py, which previously mixed this pure data with local
disk/subprocess I/O (now in infrastructure/local_storage/code_agent_store.py),
HTTP transport (now in infrastructure/anthropic_api/code_agent_loop_gateway.py),
and CLI presentation/print()/input() (now in
interfaces/cli/commands/code_agent_loop_commands.py).

Note: this module's HOOK_EVENTS / HooksEngine concept is a separate,
parallel system from domain/agent_execution.py's HookEvent /
HookManager — the original codebase had two independent hook
implementations (claude_code.py's own, and claude_hooks_perms_plan.py's).
This migration preserves that duplication rather than silently merging
them, since consolidating two live subsystems is a behavior change, not
a refactor.
"""

import os
import re
from pathlib import Path
from typing import Tuple

# ── Tool presets & permission modes ─────────────────────────────────────────

BUILTIN_TOOLS = [
    "Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep",
    "LS", "WebSearch", "WebFetch", "Task", "TodoRead", "TodoWrite",
    "NotebookRead", "NotebookEdit", "mcp__*",
]

TOOL_PRESETS = {
    "all":        BUILTIN_TOOLS,
    "code":       ["Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep", "LS"],
    "web":        ["WebSearch", "WebFetch"],
    "readonly":   ["Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch"],
    "filesystem": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "LS"],
    "safe":       ["Read", "Glob", "Grep", "LS"],
    "none":       [],
}

PERMISSION_MODES = {
    "acceptEdits":       "Auto-approve file edits; ask for other tool calls",
    "askPermission":     "Ask user before each tool call (default)",
    "bypassPermissions": "Auto-approve ALL tool calls (use with caution)",
    "dontAsk":           "Deny anything not in allowed_tools; no prompts",
    "planMode":          "Plan only — no tool execution, output a plan",
}

# Read-only tools that auto-approve under askPermission's non-interactive
# fallback (no can_use_tool callback supplied) — anything not in this set
# needs an explicit decision.
READ_ONLY_TOOLS = {"Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch", "TodoRead"}

# Built-in tool schemas for the local Messages-API agentic loop (not MCP,
# not the Anthropic Agent SDK — this project's own from-stdlib
# reimplementation of it, see CodeAgent's docstring).
TOOL_SCHEMAS = {
    "Read":      {"description": "Read a file", "input_schema": {
        "type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    "Write":     {"description": "Write a file", "input_schema": {
        "type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"]}},
    "Edit":      {"description": "Edit part of a file", "input_schema": {
        "type": "object", "properties": {
            "path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}},
        "required": ["path", "old_string", "new_string"]}},
    "Bash":      {"description": "Run a bash command", "input_schema": {
        "type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}},
        "required": ["command"]}},
    "Glob":      {"description": "Find files matching a pattern", "input_schema": {
        "type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
        "required": ["pattern"]}},
    "Grep":      {"description": "Search file contents", "input_schema": {
        "type": "object", "properties": {
            "pattern": {"type": "string"}, "path": {"type": "string"}, "include": {"type": "string"}},
        "required": ["pattern"]}},
    "LS":        {"description": "List directory contents", "input_schema": {
        "type": "object", "properties": {"path": {"type": "string"}}, "required": []}},
    "WebSearch": {"description": "Search the web", "input_schema": {
        "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    "WebFetch":  {"description": "Fetch a URL", "input_schema": {
        "type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    "TodoRead":  {"description": "Read todo list", "input_schema": {
        "type": "object", "properties": {}, "required": []}},
    "TodoWrite": {"description": "Update todo list", "input_schema": {
        "type": "object", "properties": {"todos": {"type": "array", "items": {"type": "object"}}},
        "required": ["todos"]}},
}


def build_tool_definitions(preset: str, allowed: list) -> list:
    """Pure assembly of tool definitions for the agentic loop from
    TOOL_SCHEMAS — split out of CodeAgent._build_tools() (which had no
    I/O itself, just needed the schema table alongside it)."""
    names = allowed or TOOL_PRESETS.get(preset, TOOL_PRESETS["all"])
    tools_out = []
    for name in names:
        if name == "mcp__*":
            continue
        if name in TOOL_SCHEMAS:
            tools_out.append({"name": name, **TOOL_SCHEMAS[name]})
    return tools_out


# ── Hooks (claude_code.py's own system — see module docstring) ─────────────

HOOK_EVENTS = [
    "PreToolUse", "PostToolUse", "PostToolUseFailure", "UserPromptSubmit",
    "Stop", "SubagentStart", "SubagentStop", "PreCompact", "Notification",
    "PermissionRequest", "SessionStart", "SessionEnd", "Setup",
    "TaskCompleted", "ConfigChange", "WorktreeCreate", "WorktreeRemove",
]


# ── Slash commands ───────────────────────────────────────────────────────

BUILTIN_SLASH_COMMANDS = {
    "/clear":    "Clear conversation history and start a new session",
    "/compact":  "Compact message history to save context window",
    "/help":     "Show available commands",
    "/model":    "Switch or display current model",
    "/status":   "Show current session status",
    "/cost":     "Show token usage and cost for this session",
    "/memory":   "View or edit memory (CLAUDE.md)",
    "/vim":      "Toggle vim keybindings",
    "/agents":   "List or create subagent definitions",
    "/skills":   "List available skills",
    "/mcp":      "Show MCP server status",
    "/review":   "Start a code review",
    "/doctor":   "Run diagnostics",
    "/bug":      "Report a bug",
    "/pr":       "Create a pull request",
    "/commit":   "Commit staged changes",
}

SLASH_COMMAND_ALIASES = {
    "clear": "/clear", "compact": "/compact", "help": "/help",
    "model": "/model", "status": "/status", "cost": "/cost",
    "memory": "/memory", "vim": "/vim",
}


# ── Agent Skills ─────────────────────────────────────────────────────────

ANTHROPIC_MANAGED_SKILLS = {
    "pptx": "Create PowerPoint presentations",
    "xlsx": "Create Excel spreadsheets",
    "docx": "Create Word documents",
    "pdf":  "Create and fill PDF files",
}


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    """Parse a `.claude/agents/*.md` file's YAML-ish frontmatter block.
    Pure string parsing, split out of SubagentRegistry._parse_frontmatter
    (which had no I/O of its own — the file read happens in its caller)."""
    if not content.startswith("---"):
        return {}, content
    lines = content.split("\n")
    end = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---"), None)
    if end is None:
        return {}, content
    meta = {}
    for line in lines[1:end]:
        m = re.match(r'^(\w+):\s*(.+)', line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
    body = "\n".join(lines[end + 1:])
    return meta, body


def extract_skill_description(content: str) -> str:
    """First non-frontmatter, non-blank line of a SKILL.md — pure text
    extraction, split out of SkillsRegistry.load()'s inline generator
    expression so it's independently testable."""
    return next((ln.lstrip("# ").strip() for ln in content.splitlines()
                 if ln.strip() and not ln.startswith("---")), "")


# ── Storage paths (pure Path construction, not I/O — mkdir happens in the
# infrastructure layer that actually uses these) ────────────────────────

SESSIONS_DIR  = Path(os.path.expanduser("~/.ai-coder/code_sessions"))
HOOKS_DIR     = Path(os.path.expanduser("~/.ai-coder/hooks"))
SKILLS_DIR    = Path(".claude/skills")
AGENTS_DIR    = Path(".claude/agents")
COMMANDS_DIR  = Path(".claude/commands")
MEMORY_FILE   = Path(".claude/CLAUDE.md")
USER_MEMORY   = Path(os.path.expanduser("~/.claude/CLAUDE.md"))
MCP_JSON      = Path(".mcp.json")
SETTINGS_JSON = Path(".claude/settings.json")
TODO_FILE     = Path(os.path.expanduser("~/.ai-coder/code_todos.json"))
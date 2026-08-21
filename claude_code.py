"""
claude_code.py — Claude Code / Agent SDK (compatibility shim)
AI Model Coder CLI v1.49.0 (Clean Architecture refactor, Phase C)

This module used to contain the full implementation (9 classes, ~1,440
lines: CodeSession, HooksEngine, McpConnector, SubagentRegistry,
SkillsRegistry, TodoManager, MemoryManager, CodeAgent,
StructuredAgentOutput, plus 8 cmd_* CLI entry points). It has been split
into:

  domain/code_agent.py                                    — pure data/logic
  infrastructure/local_storage/code_agent_store.py         — sessions, hooks,
                                                               MCP config,
                                                               subagents,
                                                               skills, todos,
                                                               memory (all
                                                               local-disk)
  infrastructure/anthropic_api/code_agent_loop_gateway.py  — CodeAgent /
                                                               StructuredAgentOutput
                                                               (Messages API)
  application/code_agent_loop_service.py                   — use-case layer
  interfaces/cli/commands/code_agent_loop_commands.py       — print()/input(),
                                                               the 8 cmd_*
                                                               entry points

This file re-exports every name the old module used to export, so
existing imports (`from claude_code import cmd_code_agent`, etc., in
main.py) and existing tests keep working unmodified. See
exec-planning.md §5 (migration playbook) for why this shim exists
instead of updating every call site in the same pass — main.py's own
split is deliberately deferred to Phase E.
"""

from domain.code_agent import (
    AGENTS_DIR,
    ANTHROPIC_MANAGED_SKILLS,
    BUILTIN_SLASH_COMMANDS,
    BUILTIN_TOOLS,
    COMMANDS_DIR,
    HOOK_EVENTS,
    HOOKS_DIR,
    MCP_JSON,
    MEMORY_FILE,
    PERMISSION_MODES,
    READ_ONLY_TOOLS,
    SESSIONS_DIR,
    SETTINGS_JSON,
    SKILLS_DIR,
    SLASH_COMMAND_ALIASES,
    TODO_FILE,
    TOOL_PRESETS,
    TOOL_SCHEMAS,
    USER_MEMORY,
    build_tool_definitions,
    extract_skill_description,
    parse_frontmatter,
)
from infrastructure.anthropic_api.code_agent_loop_gateway import (
    CodeAgent,
    StructuredAgentOutput,
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
from interfaces.cli.commands.code_agent_loop_commands import (
    cmd_code_agent,
    cmd_code_cost,
    cmd_code_list_sessions,
    cmd_code_list_tools,
    cmd_code_slash,
    cmd_code_subagent,
    cmd_code_todo,
)

__all__ = [
    "BUILTIN_TOOLS",
    "TOOL_PRESETS",
    "PERMISSION_MODES",
    "READ_ONLY_TOOLS",
    "HOOK_EVENTS",
    "BUILTIN_SLASH_COMMANDS",
    "SLASH_COMMAND_ALIASES",
    "ANTHROPIC_MANAGED_SKILLS",
    "TOOL_SCHEMAS",
    "build_tool_definitions",
    "parse_frontmatter",
    "extract_skill_description",
    "SESSIONS_DIR",
    "HOOKS_DIR",
    "SKILLS_DIR",
    "AGENTS_DIR",
    "COMMANDS_DIR",
    "MEMORY_FILE",
    "USER_MEMORY",
    "MCP_JSON",
    "SETTINGS_JSON",
    "TODO_FILE",
    "CodeSession",
    "HooksEngine",
    "McpConnector",
    "SubagentRegistry",
    "SkillsRegistry",
    "TodoManager",
    "MemoryManager",
    "CodeAgent",
    "StructuredAgentOutput",
    "default_can_use_tool",
    "cmd_code_agent",
    "cmd_code_subagent",
    "cmd_code_todo",
    "cmd_code_slash",
    "cmd_code_cost",
    "cmd_code_list_sessions",
    "cmd_code_list_tools",
]

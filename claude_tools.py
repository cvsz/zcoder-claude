"""
claude_tools.py — Tool Use (Function Calling) (compatibility shim)
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - SERVER_TOOLS, RETIRED_TOOL_VERSIONS, check_retired_tool_version,
    computer_use_tool_for_model, SERVER_TOOL_BETAS,
    CONTEXT_MANAGEMENT_BETA, COMPACTION_BETA, TASK_BUDGET_BETA,
    TASK_BUDGET_MODELS, ADVANCED_TOOL_USE_BETA,
    MID_CONVERSATION_TOOL_CHANGES_BETA/SUPPORTED,
    validate_mid_conversation_tool_change, with_mid_conversation_tool_changes,
    build_context_management, resume_after_compaction, build_task_budget,
    with_input_examples, with_allowed_callers, ToolRegistry
    → domain/tools.py
  - MemoryToolHandler, ToolCoder → infrastructure/anthropic_api/tools_gateway.py
  - build_code_tools_registry → application/tools_service.py
  - cmd_tool_agent, cmd_server_tool, cmd_memory_agent, cmd_list_server_tools
    → interfaces/cli/commands/tools_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from application.tools_service import build_code_tools_registry
from domain.tools import (
    ADVANCED_TOOL_USE_BETA,
    COMPACTION_BETA,
    COMPUTER_USE_TOOL_VERSIONS,
    CONTEXT_MANAGEMENT_BETA,
    MID_CONVERSATION_TOOL_CHANGES_BETA,
    MID_CONVERSATION_TOOL_CHANGES_SUPPORTED,
    RETIRED_TOOL_VERSIONS,
    SERVER_TOOL_BETAS,
    SERVER_TOOLS,
    TASK_BUDGET_BETA,
    TASK_BUDGET_MODELS,
    ToolRegistry,
    build_context_management,
    build_task_budget,
    check_retired_tool_version,
    computer_use_tool_for_model,
    resume_after_compaction,
    validate_mid_conversation_tool_change,
    with_allowed_callers,
    with_input_examples,
    with_mid_conversation_tool_changes,
)
from infrastructure.anthropic_api.tools_gateway import MemoryToolHandler, ToolCoder
from interfaces.cli.commands.tools_commands import (
    cmd_list_server_tools,
    cmd_memory_agent,
    cmd_server_tool,
    cmd_tool_agent,
)

__all__ = [
    "SERVER_TOOLS",
    "COMPUTER_USE_TOOL_VERSIONS",
    "RETIRED_TOOL_VERSIONS",
    "check_retired_tool_version",
    "computer_use_tool_for_model",
    "SERVER_TOOL_BETAS",
    "CONTEXT_MANAGEMENT_BETA",
    "COMPACTION_BETA",
    "TASK_BUDGET_BETA",
    "TASK_BUDGET_MODELS",
    "ADVANCED_TOOL_USE_BETA",
    "MID_CONVERSATION_TOOL_CHANGES_BETA",
    "MID_CONVERSATION_TOOL_CHANGES_SUPPORTED",
    "validate_mid_conversation_tool_change",
    "with_mid_conversation_tool_changes",
    "build_context_management",
    "resume_after_compaction",
    "build_task_budget",
    "with_input_examples",
    "with_allowed_callers",
    "ToolRegistry",
    "MemoryToolHandler",
    "ToolCoder",
    "build_code_tools_registry",
    "cmd_tool_agent",
    "cmd_server_tool",
    "cmd_memory_agent",
    "cmd_list_server_tools",
]

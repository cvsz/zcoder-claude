"""
claude_code_exec.py — Code Execution Tool (beta) (compatibility shim)
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - CodeExecutionCoder, CODE_EXEC_TOOL, LEGACY_BETA_HEADER,
    LEGACY_CODE_EXEC_VERSION, DEFAULT_CODE_EXEC_VERSION →
    infrastructure/anthropic_api/code_agent_gateway.py
  - cmd_code_exec, cmd_code_debug → interfaces/cli/commands/code_agent_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from infrastructure.anthropic_api.code_agent_gateway import (
    CodeExecutionCoder, CODE_EXEC_TOOL, LEGACY_BETA_HEADER,
    LEGACY_CODE_EXEC_VERSION, DEFAULT_CODE_EXEC_VERSION,
)
from interfaces.cli.commands.code_agent_commands import cmd_code_exec, cmd_code_debug

__all__ = [
    "CodeExecutionCoder", "CODE_EXEC_TOOL", "LEGACY_BETA_HEADER",
    "LEGACY_CODE_EXEC_VERSION", "DEFAULT_CODE_EXEC_VERSION",
    "cmd_code_exec", "cmd_code_debug",
]

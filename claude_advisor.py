"""
claude_advisor.py — Advisor tool (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (241 lines: AdvisorCoder,
build_advisor_tool, _strip_advisor_blocks, and cmd_advisor CLI entry point).
It has been split into:

  domain/advisor.py                                     — ADVISOR_TOOL_TYPE,
                                                          ADVISOR_TOOL_BETA,
                                                          ADVISOR_EXECUTOR_MODELS,
                                                          build_advisor_tool(),
                                                          strip_advisor_blocks()
  infrastructure/anthropic_api/advisor_gateway.py       — AdvisorGateway
  application/advisor_service.py                        — use-case layer
  interfaces/cli/commands/advisor_commands.py           — print(), cmd_advisor

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.advisor import (
    ADVISOR_TOOL_TYPE, ADVISOR_TOOL_BETA, ADVISOR_EXECUTOR_MODELS,
    build_advisor_tool, strip_advisor_blocks,
)
from infrastructure.anthropic_api.advisor_gateway import AdvisorGateway
from interfaces.cli.commands.advisor_commands import cmd_advisor

__all__ = [
    "ADVISOR_TOOL_TYPE", "ADVISOR_TOOL_BETA", "ADVISOR_EXECUTOR_MODELS",
    "build_advisor_tool", "strip_advisor_blocks",
    "AdvisorGateway",
    "cmd_advisor",
]

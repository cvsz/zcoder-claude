"""
claude_research.py — Deep Research (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (142 lines: SubQ, Report,
DeepResearchAgent, and cmd_research CLI entry point). It has been split into:

  domain/research.py                                   — SYS_PLAN, SYS_ANAL, SYS_SYNTH,
                                                          SubQ, Report,
                                                          clean_json_response(),
                                                          parse_subquestions(),
                                                          parse_findings()
  infrastructure/anthropic_api/research_gateway.py     — DeepResearchGateway
  application/research_service.py                      — use-case layer
  interfaces/cli/commands/research_commands.py         — print(), cmd_research

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.research import (
    SYS_ANAL,
    SYS_PLAN,
    SYS_SYNTH,
    Report,
    SubQ,
    clean_json_response,
    parse_findings,
    parse_subquestions,
)
from infrastructure.anthropic_api.research_gateway import DeepResearchGateway
from interfaces.cli.commands.research_commands import cmd_research

__all__ = [
    "SYS_PLAN",
    "SYS_ANAL",
    "SYS_SYNTH",
    "SubQ",
    "Report",
    "clean_json_response",
    "parse_subquestions",
    "parse_findings",
    "DeepResearchGateway",
    "cmd_research",
]

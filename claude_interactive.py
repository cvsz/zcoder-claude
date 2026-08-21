"""
claude_interactive.py — Interactive chat interface (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (116 lines: HELP_TEXT,
_format_transcript, and cmd_interactive CLI entry point). It has been split
into:

  domain/interactive.py                                  — HELP_TEXT,
                                                            format_transcript()
  application/interactive_service.py                     — use-case layer
  interfaces/cli/commands/interactive_commands.py        — print(), input(),
                                                            cmd_interactive

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.interactive import HELP_TEXT, format_transcript
from interfaces.cli.commands.interactive_commands import cmd_interactive

__all__ = ["HELP_TEXT", "format_transcript", "cmd_interactive"]

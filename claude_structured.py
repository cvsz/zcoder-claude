"""
claude_structured.py — Structured Outputs (compatibility shim)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Real implementation moved 2026-08-15:
  - StructuredCoder → infrastructure/anthropic_api/messaging_gateway.py
  - cmd_structured, cmd_structured_analyse, cmd_structured_extract →
    interfaces/cli/commands/messaging_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from infrastructure.anthropic_api.messaging_gateway import StructuredCoder
from interfaces.cli.commands.messaging_commands import (
    cmd_structured,
    cmd_structured_analyse,
    cmd_structured_extract,
)

__all__ = ["StructuredCoder", "cmd_structured", "cmd_structured_analyse", "cmd_structured_extract"]

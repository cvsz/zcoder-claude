"""
claude_citations.py — Citations & RAG (compatibility shim)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Real implementation moved 2026-08-15:
  - CitationsCoder → infrastructure/anthropic_api/messaging_gateway.py
  - cmd_cite, cmd_rag → interfaces/cli/commands/messaging_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from infrastructure.anthropic_api.messaging_gateway import CitationsCoder
from interfaces.cli.commands.messaging_commands import cmd_cite, cmd_rag

__all__ = ["CitationsCoder", "cmd_cite", "cmd_rag"]

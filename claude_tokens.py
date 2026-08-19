"""
claude_tokens.py — Token Counting (compatibility shim)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Real implementation moved 2026-08-15:
  - TokenCounter → infrastructure/anthropic_api/messaging_gateway.py
    (estimate_cost now reads domain/models/catalog.py's price table
    instead of a locally-defined one — see catalog.get_price)
  - cmd_count_tokens → interfaces/cli/commands/messaging_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from infrastructure.anthropic_api.messaging_gateway import TokenCounter
from interfaces.cli.commands.messaging_commands import cmd_count_tokens

__all__ = ["TokenCounter", "cmd_count_tokens"]

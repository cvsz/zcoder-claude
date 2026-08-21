"""
claude_thinking.py — Extended Thinking & Adaptive Thinking (compatibility shim)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Real implementation moved 2026-08-15:
  - EFFORT_BUDGETS, ADAPTIVE_THINKING_MODELS, BUDGET_TOKENS_UNSUPPORTED_MODELS,
    supports_adaptive_thinking, supports_manual_budget_tokens, ThinkingModeError
    → domain/messaging.py
  - ThinkingCoder → infrastructure/anthropic_api/messaging_gateway.py
  - cmd_thinking → interfaces/cli/commands/messaging_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.messaging import (
    ADAPTIVE_THINKING_MODELS,
    BUDGET_TOKENS_UNSUPPORTED_MODELS,
    EFFORT_BUDGETS,
    ThinkingModeError,
    supports_adaptive_thinking,
    supports_manual_budget_tokens,
)
from infrastructure.anthropic_api.messaging_gateway import ThinkingCoder
from interfaces.cli.commands.messaging_commands import cmd_thinking

__all__ = [
    "EFFORT_BUDGETS",
    "ADAPTIVE_THINKING_MODELS",
    "BUDGET_TOKENS_UNSUPPORTED_MODELS",
    "supports_adaptive_thinking",
    "supports_manual_budget_tokens",
    "ThinkingModeError",
    "ThinkingCoder",
    "cmd_thinking",
]

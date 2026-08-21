"""
claude_mythos5.py — Claude Mythos 5 support (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Real implementation moved 2026-08-21:
  - MythosAccessError → domain/model_wrappers.py
  - Mythos5Client     → infrastructure/anthropic_api/model_wrappers_gateway.py
  - cmd_mythos5_info, cmd_mythos5_call
                      → interfaces/cli/commands/wrapper_commands.py

MYTHOS5_MODEL_ID and the FABLE_MYTHOS_INFO table have always lived with
their Fable 5 sibling; they now come from domain/model_wrappers.py too.

New code should import from those locations directly rather than through
this shim.
"""

from domain.model_wrappers import MYTHOS5_MODEL_ID, MythosAccessError
from infrastructure.anthropic_api.model_wrappers_gateway import Mythos5Client
from interfaces.cli.commands.wrapper_commands import cmd_mythos5_call, cmd_mythos5_info

__all__ = ["MYTHOS5_MODEL_ID", "MythosAccessError", "Mythos5Client", "cmd_mythos5_info", "cmd_mythos5_call"]

"""
claude_live.py — Real-time streaming REPL (zai-live mode) (compatibility shim)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Real implementation moved 2026-08-15:
  - AmbientBuffer, LIVE_SYSTEM → domain/messaging.py
  - LiveSession → infrastructure/anthropic_api/messaging_gateway.py
  - cmd_live, _handle_slash → interfaces/cli/commands/messaging_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.messaging import LIVE_SYSTEM, AmbientBuffer
from infrastructure.anthropic_api.messaging_gateway import LiveSession
from interfaces.cli.commands.messaging_commands import _handle_slash, cmd_live

__all__ = ["AmbientBuffer", "LIVE_SYSTEM", "LiveSession", "cmd_live", "_handle_slash"]

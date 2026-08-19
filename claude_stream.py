"""
claude_stream.py — Streaming Messages (compatibility shim)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

This module used to hold the real implementation. As of the Phase B
migration (2026-08-15) it's a thin re-export shim so existing imports
(main.py, tests/) keep working unchanged:
  - StreamCoder, with_eager_input_streaming, handle_refusal,
    FINE_GRAINED_TOOL_STREAMING_BETA → infrastructure/anthropic_api/messaging_gateway.py
  - cmd_stream, cmd_stream_tools → interfaces/cli/commands/messaging_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.messaging import FINE_GRAINED_TOOL_STREAMING_BETA, with_eager_input_streaming, handle_refusal
from infrastructure.anthropic_api.messaging_gateway import StreamCoder
from interfaces.cli.commands.messaging_commands import cmd_stream, cmd_stream_tools

__all__ = [
    "FINE_GRAINED_TOOL_STREAMING_BETA", "with_eager_input_streaming", "handle_refusal",
    "StreamCoder", "cmd_stream", "cmd_stream_tools",
]

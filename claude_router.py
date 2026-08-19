"""
claude_router.py — Multi-Agent Conversation Router (compatibility shim)
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - DEFAULT_ROUTING_TABLE → domain/agent_execution.py
  - classify, route_and_call → infrastructure/anthropic_api/code_agent_gateway.py
  - cmd_route, cmd_route_list → interfaces/cli/commands/code_agent_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.agent_execution import DEFAULT_ROUTING_TABLE
from infrastructure.anthropic_api.code_agent_gateway import classify, route_and_call
from interfaces.cli.commands.code_agent_commands import cmd_route, cmd_route_list

__all__ = ["DEFAULT_ROUTING_TABLE", "classify", "route_and_call", "cmd_route", "cmd_route_list"]

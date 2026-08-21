"""
claude_search.py — Web Search & Web Fetch (Anthropic server tools) (compatibility shim)
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - SearchCoder, WEB_SEARCH_TOOL, WEB_FETCH_TOOL → infrastructure/anthropic_api/search_gateway.py
  - cmd_web_search, cmd_fetch_url → interfaces/cli/commands/tools_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from infrastructure.anthropic_api.search_gateway import WEB_FETCH_TOOL, WEB_SEARCH_TOOL, SearchCoder
from interfaces.cli.commands.tools_commands import cmd_fetch_url, cmd_web_search

__all__ = ["SearchCoder", "WEB_SEARCH_TOOL", "WEB_FETCH_TOOL", "cmd_web_search", "cmd_fetch_url"]

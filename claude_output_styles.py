"""
claude_output_styles.py — Output Styles (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (146 lines: built-in
styles, custom style discovery, plugin style loading, and one cmd_* CLI
entry point). It has been split into:

  domain/output_styles.py                             — BUILTIN_STYLES,
                                                        _parse_style_file(),
                                                        list_styles(), get_style(),
                                                        system_prompt_fragment()
  infrastructure/local_storage/styles_store.py        — discover_custom_styles(),
                                                        load_plugin_output_styles()
  application/output_styles_service.py                — use-case layer
  interfaces/cli/commands/output_styles_commands.py   — print(), cmd_list_output_styles

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.output_styles import (
    PROJECT_STYLES_DIR, USER_STYLES_DIR,
    BUILTIN_STYLES, FRONTMATTER_RE,
    _parse_style_file,
    list_styles, get_style, system_prompt_fragment,
)
from infrastructure.local_storage.styles_store import (
    discover_custom_styles, load_plugin_output_styles,
)
from interfaces.cli.commands.output_styles_commands import cmd_list_output_styles

__all__ = [
    "PROJECT_STYLES_DIR", "USER_STYLES_DIR",
    "BUILTIN_STYLES", "FRONTMATTER_RE",
    "_parse_style_file",
    "list_styles", "get_style", "system_prompt_fragment",
    "discover_custom_styles", "load_plugin_output_styles",
    "cmd_list_output_styles",
]

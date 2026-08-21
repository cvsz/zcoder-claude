"""application/output_styles_service.py — use-case layer for Output Styles
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/output_styles.py + infrastructure/local_storage/
styles_store.py — no print() of its own.
"""

from typing import Optional

from domain.output_styles import list_styles, get_style, system_prompt_fragment
from infrastructure.local_storage.styles_store import (
    discover_custom_styles, load_plugin_output_styles,
)


def get_all_styles(plugin_dirs: Optional[list] = None) -> list:
    custom = discover_custom_styles()
    if plugin_dirs:
        custom.update({s["name"]: s for s in load_plugin_output_styles(plugin_dirs)})
    return list_styles(list(custom.values()))


def get_style_by_name(name: str, plugin_dirs: Optional[list] = None) -> Optional[dict]:
    custom = discover_custom_styles()
    if plugin_dirs:
        custom.update({s["name"]: s for s in load_plugin_output_styles(plugin_dirs)})
    return get_style(name, custom)


def build_system_prompt_fragment(name: str, plugin_dirs: Optional[list] = None) -> str:
    custom = discover_custom_styles()
    if plugin_dirs:
        custom.update({s["name"]: s for s in load_plugin_output_styles(plugin_dirs)})
    return system_prompt_fragment(name, custom)

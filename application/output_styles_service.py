"""application/output_styles_service.py — use-case layer for Output Styles
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/output_styles.py + infrastructure/local_storage/
styles_store.py — no print() of its own.
"""

from domain.output_styles import get_style, list_styles, system_prompt_fragment
from infrastructure.local_storage.styles_store import (
    discover_custom_styles,
    load_plugin_output_styles,
)


def get_all_styles(plugin_dirs: list | None = None) -> list:
    custom = discover_custom_styles()
    if plugin_dirs:
        custom.update({s["name"]: s for s in load_plugin_output_styles(plugin_dirs)})
    return list_styles(list(custom.values()))


def get_style_by_name(name: str, plugin_dirs: list | None = None) -> dict | None:
    custom = discover_custom_styles()
    if plugin_dirs:
        custom.update({s["name"]: s for s in load_plugin_output_styles(plugin_dirs)})
    return get_style(name, custom)


def build_system_prompt_fragment(name: str, plugin_dirs: list | None = None) -> str:
    custom = discover_custom_styles()
    if plugin_dirs:
        custom.update({s["name"]: s for s in load_plugin_output_styles(plugin_dirs)})
    return system_prompt_fragment(name, custom)

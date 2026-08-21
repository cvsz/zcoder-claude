"""application/plugins_service.py — use-case layer for Plugins & Marketplace
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/plugins.py + infrastructure/local_storage/plugins_store.py
— no print() of its own.
"""

from pathlib import Path
from typing import Optional

from domain.plugins import (
    enabled_plugin_dirs,
    load_plugin_skills, load_plugin_commands, load_plugin_agents,
    load_plugin_output_styles, load_plugin_hooks, load_plugin_mcp_servers,
    plugin_bin_paths,
    validate_plugin,
)
from infrastructure.local_storage.plugins_store import (
    marketplace_add, marketplace_list, marketplace_remove,
    plugin_install, plugin_install_from_dir, plugin_uninstall,
    plugin_set_enabled, plugin_list, plugin_info,
)


def get_plugin_dirs(reg: Optional[dict] = None) -> list:
    reg = reg or _load_registry()
    return enabled_plugin_dirs(reg.get("installed", {}))


def _load_registry() -> dict:
    from infrastructure.local_storage.plugins_store import _load_registry
    return _load_registry()


def add_marketplace(source: str, name: Optional[str] = None) -> dict:
    return marketplace_add(source, name)


def list_marketplaces() -> list:
    return marketplace_list()


def remove_marketplace(name: str) -> bool:
    return marketplace_remove(name)


def install_plugin(spec: str) -> dict:
    reg = _load_registry()
    return plugin_install(spec, reg)


def install_plugin_from_dir(path: str) -> dict:
    reg = _load_registry()
    return plugin_install_from_dir(path, reg)


def uninstall_plugin(name: str) -> bool:
    reg = _load_registry()
    return plugin_uninstall(name, reg)


def set_plugin_enabled(name: str, enabled: bool) -> bool:
    reg = _load_registry()
    return plugin_set_enabled(name, enabled, reg)


def list_plugins() -> list:
    return plugin_list(_load_registry())


def get_plugin_info(name: str) -> Optional[dict]:
    return plugin_info(name, _load_registry())


def validate_plugin_dir(path: str) -> list:
    return validate_plugin(Path(path).expanduser())


def get_enabled_skills() -> list:
    return load_plugin_skills(get_plugin_dirs())


def get_enabled_commands() -> list:
    return load_plugin_commands(get_plugin_dirs())


def get_enabled_agents() -> list:
    return load_plugin_agents(get_plugin_dirs())


def get_enabled_output_styles() -> list:
    return load_plugin_output_styles(get_plugin_dirs())


def get_enabled_hooks() -> dict:
    return load_plugin_hooks(get_plugin_dirs())


def get_enabled_mcp_servers() -> dict:
    return load_plugin_mcp_servers(get_plugin_dirs())


def get_plugin_bin_paths() -> list:
    return plugin_bin_paths(get_plugin_dirs())

"""
claude_plugins.py — Plugin & Marketplace system (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

This module used to contain the full implementation (631 lines: plugin
registry, manifest parsing, marketplace add/list/remove, install/uninstall,
plugin loading, and 10 cmd_* CLI entry points). It has been split into:

  domain/plugins.py                                      — DEFAULT_MANIFEST_FIELDS,
                                                          read_manifest(),
                                                          validate_plugin(),
                                                          discover_plugins_in_marketplace(),
                                                          load_plugin_*()
  infrastructure/local_storage/plugins_store.py          — _load_registry(),
                                                          _save_registry(),
                                                          marketplace_add(), etc.
  application/plugins_service.py                         — use-case layer
  interfaces/cli/commands/plugins_commands.py            — print(), cmd_plugin_*

This file re-exports every name the old module used to export, so
existing imports keep working unmodified.
"""

from domain.plugins import (
    PLUGINS_ROOT, MARKETPLACES_DIR, INSTALLED_DIR, REGISTRY_FILE,
    DEFAULT_MANIFEST_FIELDS,
    read_manifest, validate_plugin,
    _is_url, discover_plugins_in_marketplace,
    enabled_plugin_dirs,
    load_plugin_skills, load_plugin_commands, load_plugin_agents,
    load_plugin_output_styles, load_plugin_hooks, load_plugin_mcp_servers,
    plugin_bin_paths,
)
from infrastructure.local_storage.plugins_store import (
    _load_registry, _save_registry,
    marketplace_add, marketplace_list, marketplace_remove,
    plugin_install, plugin_install_from_dir, plugin_uninstall,
    plugin_set_enabled, plugin_list, plugin_info,
)
from interfaces.cli.commands.plugins_commands import (
    cmd_plugin_marketplace_add, cmd_plugin_marketplace_list,
    cmd_plugin_marketplace_remove,
    cmd_plugin_install, cmd_plugin_install_dir, cmd_plugin_uninstall,
    cmd_plugin_list, cmd_plugin_info,
    cmd_plugin_enable, cmd_plugin_disable, cmd_plugin_validate,
)

__all__ = [
    "PLUGINS_ROOT", "MARKETPLACES_DIR", "INSTALLED_DIR", "REGISTRY_FILE",
    "DEFAULT_MANIFEST_FIELDS",
    "read_manifest", "validate_plugin",
    "_is_url", "discover_plugins_in_marketplace",
    "enabled_plugin_dirs",
    "load_plugin_skills", "load_plugin_commands", "load_plugin_agents",
    "load_plugin_output_styles", "load_plugin_hooks", "load_plugin_mcp_servers",
    "plugin_bin_paths",
    "_load_registry", "_save_registry",
    "marketplace_add", "marketplace_list", "marketplace_remove",
    "plugin_install", "plugin_install_from_dir", "plugin_uninstall",
    "plugin_set_enabled", "plugin_list", "plugin_info",
    "cmd_plugin_marketplace_add", "cmd_plugin_marketplace_list",
    "cmd_plugin_marketplace_remove",
    "cmd_plugin_install", "cmd_plugin_install_dir", "cmd_plugin_uninstall",
    "cmd_plugin_list", "cmd_plugin_info",
    "cmd_plugin_enable", "cmd_plugin_disable", "cmd_plugin_validate",
]

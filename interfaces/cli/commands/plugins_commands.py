"""interfaces/cli/commands/plugins_commands.py — CLI presentation for Plugins & Marketplace
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/plugins_service.py.
"""

import sys
from pathlib import Path
from typing import Optional

from application import plugins_service as service


def cmd_plugin_marketplace_add(source: str, name: Optional[str] = None):
    try:
        info = service.add_marketplace(source, name)
        print(f"\\033[92m✓ Marketplace added: {name or Path(source.rstrip('/')).stem}\\033[0m")
        print(f"  plugins found: {', '.join(info['plugins']) or '(none)'}")
    except Exception as e:
        print(f"\\033[91m✗ {e}\\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_marketplace_list():
    mps = service.list_marketplaces()
    if not mps:
        print("No marketplaces registered. Use --plugin-marketplace-add PATH_OR_URL")
        return
    for mp in mps:
        print(f"\\033[1m{mp['name']}\\033[0m  ({mp['source']})")
        for p in mp["plugins"]:
            print(f"   • {p}")


def cmd_plugin_marketplace_remove(name: str):
    if service.remove_marketplace(name):
        print(f"\\033[92m✓ Removed marketplace: {name}\\033[0m")
    else:
        print(f"\\033[91m✗ No such marketplace: {name}\\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_install(spec: str):
    try:
        info = service.install_plugin(spec)
        print(f"\\033[92m✓ Installed {spec}\\033[0m (v{info['version']})")
    except Exception as e:
        print(f"\\033[91m✗ {e}\\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_install_dir(path: str):
    try:
        info = service.install_plugin_from_dir(path)
        print(f"\\033[92m✓ Installed from {path}\\033[0m (v{info['version']})")
    except Exception as e:
        print(f"\\033[91m✗ {e}\\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_uninstall(name: str):
    if service.uninstall_plugin(name):
        print(f"\\033[92m✓ Uninstalled {name}\\033[0m")
    else:
        print(f"\\033[91m✗ Not installed: {name}\\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_list():
    plugins = service.list_plugins()
    if not plugins:
        print("No plugins installed. Use --plugin-install NAME@MARKETPLACE")
        return
    for p in plugins:
        state = "\\033[92menabled\\033[0m" if p.get("enabled", True) else "\\033[90mdisabled\\033[0m"
        mp = p.get("marketplace") or "local"
        print(f"  {p['name']:<24} v{p['version']:<10} [{mp}]  {state}")


def cmd_plugin_info(name: str):
    info = service.get_plugin_info(name)
    if not info:
        print(f"\\033[91m✗ Not installed: {name}\\033[0m", file=sys.stderr)
        sys.exit(1)
    m = info["manifest"]
    print(f"\\033[1m{m.get('displayName') or name}\\033[0m  v{info['version']}")
    print(f"  {m.get('description', '')}")
    print(f"  marketplace: {info.get('marketplace') or 'local'}")
    print(f"  path: {info['path']}")
    plug_dir = Path(info["path"])
    for sub, label in [("skills", "Skills"), ("commands", "Commands"),
                        ("agents", "Agents"), ("output-styles", "Output styles"),
                        ("hooks", "Hooks"), (".mcp.json", "MCP servers")]:
        p = plug_dir / sub
        if p.exists():
            print(f"  • {label}: {p}")


def cmd_plugin_enable(name: str):
    if service.set_plugin_enabled(name, True):
        print(f"\\033[92m✓ Enabled {name}\\033[0m")
    else:
        print(f"\\033[91m✗ Not installed: {name}\\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_disable(name: str):
    if service.set_plugin_enabled(name, False):
        print(f"\\033[92m✓ Disabled {name}\\033[0m")
    else:
        print(f"\\033[91m✗ Not installed: {name}\\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_validate(path: str):
    findings = service.validate_plugin_dir(path)
    icon = {"ok": "\\033[92m✓", "info": "\\033[94mℹ", "warn": "\\033[93m⚠", "error": "\\033[91m✗"}
    for level, msg in findings:
        print(f"{icon.get(level, '')} {msg}\\033[0m")
    if any(level == "error" for level, _ in findings):
        sys.exit(1)

"""domain/plugins.py — Plugin & Marketplace domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for plugin management. No I/O, no print() —
those belong to infrastructure/.
"""

import json
from pathlib import Path

PLUGINS_ROOT = Path("~/.claude/plugins").expanduser()
MARKETPLACES_DIR = PLUGINS_ROOT / "marketplaces"
INSTALLED_DIR = PLUGINS_ROOT / "installed"
REGISTRY_FILE = PLUGINS_ROOT / "registry.json"

DEFAULT_MANIFEST_FIELDS = {
    "name": "", "displayName": "", "version": "0.0.0", "description": "",
    "author": {}, "homepage": "", "repository": "", "license": "",
    "keywords": [], "skills": None, "commands": None, "agents": None,
    "hooks": None, "mcpServers": None, "outputStyles": None,
    "lspServers": None, "dependencies": [],
}


def read_manifest(plugin_dir: Path) -> dict:
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text())
        except Exception as e:
            raise ValueError(f"invalid plugin.json: {e}")
        merged = {**DEFAULT_MANIFEST_FIELDS, **data}
        if not merged["name"]:
            raise ValueError("plugin.json must include a 'name' field")
        return merged
    return {
        **DEFAULT_MANIFEST_FIELDS,
        "name": plugin_dir.name,
        "displayName": plugin_dir.name,
        "description": f"Auto-discovered plugin from {plugin_dir.name}",
    }


def validate_plugin(plugin_dir: Path) -> list:
    findings = []
    if not plugin_dir.exists():
        return [("error", f"path does not exist: {plugin_dir}")]

    try:
        manifest = read_manifest(plugin_dir)
    except ValueError as e:
        return [("error", str(e))]

    if not (plugin_dir / ".claude-plugin" / "plugin.json").exists():
        findings.append(("info", "no manifest found; using auto-discovery"))

    known_dirs = {"skills", "commands", "agents", "output-styles", "themes",
                  "monitors", "hooks", "bin", "scripts"}
    for child in plugin_dir.iterdir():
        if child.is_dir() and child.name not in known_dirs and child.name != ".claude-plugin":
            findings.append(("warn", f"unrecognised top-level directory: {child.name}/"))

    hooks_json = plugin_dir / "hooks" / "hooks.json"
    if hooks_json.exists():
        try:
            json.loads(hooks_json.read_text())
        except Exception as e:
            findings.append(("error", f"hooks/hooks.json invalid JSON: {e}"))

    mcp_json = plugin_dir / ".mcp.json"
    if mcp_json.exists():
        try:
            data = json.loads(mcp_json.read_text())
            if "mcpServers" not in data:
                findings.append(("warn", ".mcp.json present but has no 'mcpServers' key"))
        except Exception as e:
            findings.append(("error", f".mcp.json invalid JSON: {e}"))

    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        for sk in skills_dir.iterdir():
            if sk.is_dir() and not (sk / "SKILL.md").exists():
                findings.append(("warn", f"skills/{sk.name}/ has no SKILL.md"))

    if not findings:
        findings.append(("ok", f"plugin '{manifest['name']}' looks valid"))
    return findings


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://") or s.startswith("git@")


def discover_plugins_in_marketplace(mp_dir: Path) -> list:
    if (mp_dir / ".claude-plugin" / "plugin.json").exists():
        return [mp_dir]
    found = []
    index = mp_dir / "marketplace.json"
    if index.exists():
        try:
            data = json.loads(index.read_text())
            for entry in data.get("plugins", []):
                rel = entry.get("path", entry.get("name", ""))
                cand = mp_dir / rel
                if cand.exists():
                    found.append(cand)
        except Exception:
            pass
    if found:
        return found
    for child in mp_dir.iterdir():
        if child.is_dir() and (
            (child / ".claude-plugin" / "plugin.json").exists()
            or (child / "skills").exists()
            or (child / "commands").exists()
            or (child / "agents").exists()
        ):
            found.append(child)
    return found


def enabled_plugin_dirs(installed: dict) -> list:
    return [Path(info["path"]) for info in installed.values() if info.get("enabled", True)]


def load_plugin_skills(plugin_dirs: list) -> list:
    out = []
    for plug_dir in plugin_dirs:
        skills_dir = plug_dir / "skills"
        if not skills_dir.exists():
            continue
        for sk in skills_dir.iterdir():
            md = sk / "SKILL.md"
            if md.exists():
                out.append({"name": sk.name, "path": str(md), "plugin": plug_dir.name})
    return out


def load_plugin_commands(plugin_dirs: list) -> list:
    out = []
    for plug_dir in plugin_dirs:
        cmd_dir = plug_dir / "commands"
        if not cmd_dir.exists():
            continue
        for f in cmd_dir.rglob("*.md"):
            out.append({
                "name": f"{plug_dir.name}:{f.stem}",
                "path": str(f),
                "plugin": plug_dir.name,
            })
    return out


def load_plugin_agents(plugin_dirs: list) -> list:
    out = []
    for plug_dir in plugin_dirs:
        agents_dir = plug_dir / "agents"
        if not agents_dir.exists():
            continue
        for f in agents_dir.glob("*.md"):
            out.append({"name": f.stem, "path": str(f), "plugin": plug_dir.name})
    return out


def load_plugin_output_styles(plugin_dirs: list) -> list:
    out = []
    for plug_dir in plugin_dirs:
        styles_dir = plug_dir / "output-styles"
        if not styles_dir.exists():
            continue
        for f in styles_dir.glob("*.md"):
            out.append({"name": f.stem, "path": str(f), "plugin": plug_dir.name})
    return out


def load_plugin_hooks(plugin_dirs: list) -> dict:
    merged = {}
    for plug_dir in plugin_dirs:
        hooks_file = plug_dir / "hooks" / "hooks.json"
        if not hooks_file.exists():
            continue
        try:
            data = json.loads(hooks_file.read_text())
        except Exception:
            continue
        for event, handlers in data.items():
            merged.setdefault(event, [])
            for h in handlers:
                h = dict(h)
                h["_plugin"] = plug_dir.name
                merged[event].append(h)
    return merged


def load_plugin_mcp_servers(plugin_dirs: list) -> dict:
    merged = {}
    for plug_dir in plugin_dirs:
        mcp_file = plug_dir / ".mcp.json"
        if not mcp_file.exists():
            continue
        try:
            data = json.loads(mcp_file.read_text())
        except Exception:
            continue
        for name, cfg in data.get("mcpServers", {}).items():
            merged[f"{plug_dir.name}:{name}"] = cfg
    return merged


def plugin_bin_paths(plugin_dirs: list) -> list:
    return [str(p / "bin") for p in plugin_dirs if (p / "bin").exists()]

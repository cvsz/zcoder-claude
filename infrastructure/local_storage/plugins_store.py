"""infrastructure/local_storage/plugins_store.py — Plugin local-disk persistence
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Local-disk I/O for plugin registry, marketplace fetching, and plugin
install/uninstall. No network calls beyond marketplace fetch, no print().
"""

# mypy: ignore-errors

import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from domain.plugins import (
    INSTALLED_DIR,
    MARKETPLACES_DIR,
    REGISTRY_FILE,
    _is_url,
    discover_plugins_in_marketplace,
    read_manifest,
)
from exceptions import TransientAPIError, ZCoderError
from infrastructure.anthropic_api.http_client import retry


def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text())
        except Exception:
            pass
    return {"marketplaces": {}, "installed": {}}


def _save_registry(reg: dict):
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(reg, indent=2))


@retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
def fetch_marketplace_source(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        raise TransientAPIError(f"could not fetch {url}: {e}") from e


def marketplace_add(source: str, name: str | None = None) -> dict:
    reg = _load_registry()
    mp_name = name or Path(source.rstrip("/")).stem or "marketplace"
    dest = MARKETPLACES_DIR / mp_name
    if dest.exists():
        shutil.rmtree(dest)

    if _is_url(source):
        if source.endswith(".zip"):
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                try:
                    tmp.write(fetch_marketplace_source(source))
                except ZCoderError as e:
                    raise RuntimeError(str(e.message)) from e
                tmp_path = tmp.name
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(dest)
            Path(tmp_path).unlink()
        else:
            try:
                raw = fetch_marketplace_source(source).decode("utf-8", errors="replace")
            except ZCoderError as e:
                raise RuntimeError(str(e.message)) from e
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "marketplace.json").write_text(raw)
    else:
        src_path = Path(source).expanduser()
        if not src_path.exists():
            raise RuntimeError(f"local path does not exist: {src_path}")
        if src_path.suffix == ".zip":
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(src_path) as zf:
                zf.extractall(dest)
        else:
            shutil.copytree(src_path, dest)

    plugins = discover_plugins_in_marketplace(dest)
    plugin_names = []
    for p in plugins:
        try:
            plugin_names.append(read_manifest(p)["name"])
        except ValueError:
            plugin_names.append(p.name)
    reg["marketplaces"][mp_name] = {
        "source": source,
        "path": str(dest),
        "plugins": plugin_names,
    }
    _save_registry(reg)
    return reg["marketplaces"][mp_name]


def marketplace_list() -> list:
    reg = _load_registry()
    out = []
    for name, info in reg["marketplaces"].items():
        out.append({"name": name, **info})
    return out


def marketplace_remove(name: str) -> bool:
    reg = _load_registry()
    if name not in reg["marketplaces"]:
        return False
    path = Path(reg["marketplaces"][name]["path"])
    if path.exists():
        shutil.rmtree(path)
    del reg["marketplaces"][name]
    for pname, pinfo in list(reg["installed"].items()):
        if pinfo.get("marketplace") == name:
            del reg["installed"][pname]
    _save_registry(reg)
    return True


def plugin_install(spec: str, reg: dict) -> dict:
    if "@" in spec:
        name, mp_name = spec.split("@", 1)
    else:
        name, mp_name = spec, None

    candidates = []
    marketplaces = [mp_name] if mp_name else list(reg["marketplaces"].keys())
    for mp in marketplaces:
        mp_info = reg["marketplaces"].get(mp)
        if not mp_info:
            continue
        mp_path = Path(mp_info["path"])
        for plug_dir in discover_plugins_in_marketplace(mp_path):
            try:
                manifest = read_manifest(plug_dir)
            except ValueError:
                continue
            if manifest["name"] == name:
                candidates.append((mp, plug_dir, manifest))

    if not candidates:
        raise RuntimeError(
            f"plugin '{name}' not found in "
            f"{'marketplace ' + mp_name if mp_name else 'any registered marketplace'}"
        )

    mp, plug_dir, manifest = candidates[0]
    dest = INSTALLED_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(plug_dir, dest)

    reg["installed"][name] = {
        "marketplace": mp,
        "version": manifest.get("version", "0.0.0"),
        "path": str(dest),
        "enabled": True,
    }
    _save_registry(reg)
    return reg["installed"][name]


def plugin_install_from_dir(path: str, reg: dict) -> dict:
    src_path = Path(path).expanduser()
    if not src_path.exists():
        raise RuntimeError(f"path does not exist: {src_path}")

    if src_path.suffix == ".zip":
        tmp_extract = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(src_path) as zf:
            zf.extractall(tmp_extract)
        contents = list(tmp_extract.iterdir())
        plug_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else tmp_extract
    else:
        plug_dir = src_path

    manifest = read_manifest(plug_dir)
    name = manifest["name"]
    dest = INSTALLED_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(plug_dir, dest)

    reg["installed"][name] = {
        "marketplace": None,
        "version": manifest.get("version", "0.0.0"),
        "path": str(dest),
        "enabled": True,
    }
    _save_registry(reg)
    return reg["installed"][name]


def plugin_uninstall(name: str, reg: dict) -> bool:
    if name not in reg["installed"]:
        return False
    path = Path(reg["installed"][name]["path"])
    if path.exists():
        shutil.rmtree(path)
    del reg["installed"][name]
    _save_registry(reg)
    return True


def plugin_set_enabled(name: str, enabled: bool, reg: dict) -> bool:
    if name not in reg["installed"]:
        return False
    reg["installed"][name]["enabled"] = enabled
    _save_registry(reg)
    return True


def plugin_list(reg: dict) -> list:
    out = []
    for name, info in reg["installed"].items():
        out.append({"name": name, **info})
    return out


def plugin_info(name: str, reg: dict) -> dict | None:
    info = reg["installed"].get(name)
    if not info:
        return None
    plug_dir = Path(info["path"])
    try:
        manifest = read_manifest(plug_dir)
    except ValueError:
        manifest = {}
    return {"name": name, **info, "manifest": manifest}

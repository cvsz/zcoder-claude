"""tests/integration/infrastructure/test_plugins_store.py

Regression coverage for the plugin registry/list path.

Root cause being guarded against: plugins_store.py once imported
TransientAPIError from `resilience` (a shim that never re-exported it),
so importing the module raised ImportError — and every plugin-loading
call site wraps imports in try/ImportError, so plugin loading silently
no-oped at runtime while --plugin-list still printed "No plugins
installed."

These tests pin down that (a) the module imports cleanly with its real
dependency graph, and (b) marketplace add + list + install + list round-
trip through the application service return actual data on a throwaway
plugins root (path constants patched to tmp_path — no touching the real
~/.claude/plugins).
"""

from pathlib import Path

import pytest

import domain.plugins as domain_plugins


@pytest.fixture
def plugins_root(tmp_path, monkeypatch):
    """Point every plugins path constant at a throwaway root. Both modules
    need patching: domain.plugins owns the constants and
    infrastructure.local_storage.plugins_store binds them by value."""
    root = tmp_path / "plugins"
    monkeypatch.setattr(domain_plugins, "PLUGINS_ROOT", root)
    monkeypatch.setattr(domain_plugins, "MARKETPLACES_DIR", root / "marketplaces")
    monkeypatch.setattr(domain_plugins, "INSTALLED_DIR", root / "installed")
    monkeypatch.setattr(domain_plugins, "REGISTRY_FILE", root / "registry.json")
    import infrastructure.local_storage.plugins_store as store

    for name in ("MARKETPLACES_DIR", "INSTALLED_DIR", "REGISTRY_FILE"):
        monkeypatch.setattr(store, name, getattr(domain_plugins, name))
    return root


def test_plugins_store_imports_cleanly():
    """The import itself must not raise — a swallowed ImportError here is
    exactly the silent no-op this file exists to prevent."""
    import core.exceptions as exceptions
    import infrastructure.local_storage.plugins_store as store

    # TransientAPIError comes from its real home, not the resilience shim.
    assert store.TransientAPIError is exceptions.TransientAPIError
    assert callable(store.retry)


def test_marketplace_add_and_list_return_data(plugins_root):
    mp_dir = plugins_root.parent / "src-mp"
    _make_plugin(mp_dir, "alpha")
    from infrastructure.local_storage.plugins_store import (
        marketplace_add,
        marketplace_list,
    )

    info = marketplace_add(str(mp_dir))
    assert info["plugins"] == ["alpha"]

    listed = marketplace_list()
    assert len(listed) == 1
    assert listed[0]["name"] == "src-mp"
    assert listed[0]["source"] == str(mp_dir)
    assert listed[0]["plugins"] == ["alpha"]


def test_registry_list_path_returns_installed_plugin(plugins_root):
    mp_dir = plugins_root.parent / "src-mp"
    _make_plugin(mp_dir, "beta")

    from application.plugins_service import install_plugin, list_plugins
    from infrastructure.local_storage.plugins_store import marketplace_add

    marketplace_add(str(mp_dir))
    installed = install_plugin("beta@src-mp")
    assert installed["marketplace"] == "src-mp"
    assert installed["enabled"] is True
    assert Path(installed["path"]).is_dir()

    plugins = list_plugins()
    assert [p["name"] for p in plugins] == ["beta"]
    assert plugins[0]["version"] == "0.1.0"


def _make_plugin(root: Path, name: str) -> None:
    manifest_dir = root / name / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        f'{{"name": "{name}", "displayName": "{name.title()}", "version": "0.1.0"}}'
    )

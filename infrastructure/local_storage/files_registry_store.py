"""
infrastructure/local_storage/files_registry_store.py — local-disk
registry of uploaded Files API file metadata
AI Model Coder CLI v1.50.0 (Clean Architecture refactor, Phase C, Context #4)

Extracted 2026-08-18 from claude_files.py's FilesAPI._load_registry()/
_register()/_unregister()/list_local(). The Files API itself has no
"list files I uploaded from this machine, with their local paths"
endpoint — it only returns what's on Anthropic's servers — so this is
purely a local convenience cache, same filesystem-adapter role as
infrastructure/local_storage/rag_index_store.py.
"""

import json
import os
from pathlib import Path

LOCAL_REGISTRY = Path(os.path.expanduser("~/.zcoder/files_registry.json"))


def load_registry() -> dict:
    if LOCAL_REGISTRY.exists():
        try:
            return json.loads(LOCAL_REGISTRY.read_text())
        except Exception:
            pass
    return {}


def ensure_registry_dir():
    """Original FilesAPI.__init__ created ~/.zcoder/ eagerly, on
    every FilesAPI() construction, not lazily on first write — some
    callers may rely on the directory existing right after
    construction, before any upload/delete happens."""
    LOCAL_REGISTRY.parent.mkdir(parents=True, exist_ok=True)


def register_file(api_result: dict, local_path: str):
    ensure_registry_dir()
    reg = load_registry()
    reg[api_result["id"]] = {
        "id": api_result["id"],
        "filename": api_result.get("filename", ""),
        "local_path": local_path,
        "created_at": api_result.get("created_at", ""),
        "size": api_result.get("size", 0),
    }
    LOCAL_REGISTRY.write_text(json.dumps(reg, indent=2))


def unregister_file(file_id: str):
    ensure_registry_dir()
    reg = load_registry()
    reg.pop(file_id, None)
    LOCAL_REGISTRY.write_text(json.dumps(reg, indent=2))


def list_local() -> dict:
    return load_registry()

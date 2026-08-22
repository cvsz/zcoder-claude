"""
infrastructure/local_storage/batch_store.py — local-disk metadata cache
for submitted batches
AI Model Coder CLI v1.52.0 (Clean Architecture refactor, Phase C, Context #4)

Extracted 2026-08-18 from claude_batch.py's BATCH_STORE constant and
BatchCoder._save_batch_meta(). The Batch API itself doesn't return the
source JSONL path or submission time on later `status`/`list` calls —
this is purely a local convenience record, same role as
infrastructure/local_storage/files_registry_store.py.
"""

import json
import os
from pathlib import Path

BATCH_STORE = Path(os.path.expanduser("~/.zcoder/batches"))


def ensure_store_dir():
    BATCH_STORE.mkdir(parents=True, exist_ok=True)


def save_batch_meta(batch_id: str, meta: dict):
    ensure_store_dir()
    (BATCH_STORE / f"{batch_id}.json").write_text(json.dumps(meta, indent=2))

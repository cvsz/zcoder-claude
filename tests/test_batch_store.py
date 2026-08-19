"""tests/test_batch_store.py

Covers infrastructure/local_storage/batch_store.py — the local-disk
submission-metadata cache, extracted 2026-08-18 (Phase C, Context #4).
"""

import json

import infrastructure.local_storage.batch_store as store


def test_save_batch_meta_writes_json(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "BATCH_STORE", tmp_path)
    store.save_batch_meta("batch_123", {"id": "batch_123", "count": 5})

    written = json.loads((tmp_path / "batch_123.json").read_text())
    assert written == {"id": "batch_123", "count": 5}


def test_ensure_store_dir_creates_missing_directory(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "batches"
    monkeypatch.setattr(store, "BATCH_STORE", target)
    assert not target.exists()
    store.ensure_store_dir()
    assert target.is_dir()

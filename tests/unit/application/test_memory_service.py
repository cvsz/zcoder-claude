"""tests/unit/application/test_memory_service.py

Covers application/memory_service.py, extracted 2026-08-18 (Phase C,
Context #5). Fake MemoryStore substituted in.
"""

import application.memory_service as service
from domain.memory import MemEntry, MemType


class FakeMemoryStore:
    instances = []

    def __init__(self, ns="default"):
        self.ns = ns
        self.entries = []
        FakeMemoryStore.instances.append(self)

    def add(self, content, mtype=MemType.FACT, tags=None, importance=5):
        e = MemEntry(content=content, mtype=mtype, tags=tags or [], importance=importance)
        self.entries.append(e)
        return e

    def recall(self, query, limit):
        self.recall_args = (query, limit)
        return [self.entries[0]] if self.entries else []

    def forget(self, mid):
        self.forgot = mid
        return mid == "existing"

    def stats(self):
        return {"total": len(self.entries), "by_type": {}, "namespace": self.ns}

    def enforce_retention(self, max_age_days, max_entries, protect_above=9):
        self.retention_args = (max_age_days, max_entries)
        return {"removed_age": 1, "removed_cap": 2}


def setup_function(_):
    FakeMemoryStore.instances.clear()


def test_add_memory_delegates(monkeypatch):
    monkeypatch.setattr(service, "MemoryStore", FakeMemoryStore)
    entry = service.add_memory("likes tea", mtype="preference", tags=["drink"], importance=7, ns="alice")
    assert entry.content == "likes tea"
    assert entry.mtype == MemType.PREFERENCE
    assert FakeMemoryStore.instances[0].ns == "alice"


def test_recall_memories_delegates(monkeypatch):
    monkeypatch.setattr(service, "MemoryStore", FakeMemoryStore)
    fake = FakeMemoryStore()
    monkeypatch.setattr(service, "MemoryStore", lambda ns: fake)
    fake.add("hi")

    hits = service.recall_memories("hi", ns="default", limit=3)
    assert len(hits) == 1
    assert fake.recall_args == ("hi", 3)


def test_forget_memory_delegates(monkeypatch):
    monkeypatch.setattr(service, "MemoryStore", FakeMemoryStore)
    assert service.forget_memory("existing") is True
    assert service.forget_memory("missing") is False


def test_get_stats_delegates(monkeypatch):
    monkeypatch.setattr(service, "MemoryStore", FakeMemoryStore)
    s = service.get_stats(ns="bob")
    assert s["namespace"] == "bob"


def test_apply_retention_returns_counts_and_remaining(monkeypatch):
    fake = FakeMemoryStore()
    fake.entries = [MemEntry(), MemEntry()]
    monkeypatch.setattr(service, "MemoryStore", lambda ns: fake)

    result, remaining = service.apply_retention(ns="default", max_age_days=100, max_entries=50)
    assert result == {"removed_age": 1, "removed_cap": 2}
    assert remaining == 2
    assert fake.retention_args == (100, 50)

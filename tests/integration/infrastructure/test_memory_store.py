"""tests/test_memory_store.py

Covers infrastructure/local_storage/memory_store.py's MemoryStore,
extracted 2026-08-18 (Phase C, Context #5) from claude_memory.py. Uses
real disk I/O against tmp_path — no mocks. Includes a regression test
for the dead-code fix made during this migration (a `prot` variable in
enforce_retention() that was computed but never used, per pyflakes on
the original untouched source).
"""

from datetime import datetime, timedelta

import infrastructure.local_storage.memory_store as store_mod
from domain.memory import MemType


def _store(tmp_path, monkeypatch, ns="default"):
    monkeypatch.setattr(store_mod, "MEMORY_DIR", tmp_path)
    return store_mod.MemoryStore(ns)


def test_add_and_persist_across_instances(tmp_path, monkeypatch):
    s1 = _store(tmp_path, monkeypatch)
    s1.add("likes coffee", MemType.PREFERENCE, importance=6)

    s2 = _store(tmp_path, monkeypatch)
    assert len(s2.entries) == 1
    assert s2.entries[0].content == "likes coffee"


def test_recall_ranks_keyword_matches_above_unrelated_entries(tmp_path, monkeypatch):
    """recall()'s score always has an importance-based floor (score =
    overlap + tag_hit*2 + importance*0.1), so every entry technically
    scores > 0 and could appear — this checks ranking, not filtering:
    the keyword-matching entry should rank first."""
    s = _store(tmp_path, monkeypatch)
    s.add("prefers dark roast coffee", MemType.PREFERENCE, tags=["coffee"])
    s.add("works remotely from home", MemType.FACT)

    hits = s.recall("coffee", limit=1)
    assert len(hits) == 1
    assert "coffee" in hits[0].content


def test_recall_marks_accessed_timestamp(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    e = s.add("likes tea")
    assert e.accessed is None
    s.recall("tea")
    assert s.entries[0].accessed is not None


def test_forget_removes_entry(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    e = s.add("temporary fact")
    assert s.forget(e.mid) is True
    assert len(s.entries) == 0


def test_forget_missing_returns_false(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    assert s.forget("nonexistent") is False


def test_context_block_empty_when_no_hits(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    assert s.context_block("anything") == ""


def test_context_block_formats_hits(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add("likes espresso", MemType.PREFERENCE)
    block = s.context_block("espresso")
    assert "## Memory Context" in block
    assert "[preference] likes espresso" in block


def test_stats_counts_by_type(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    s.add("fact one", MemType.FACT)
    s.add("fact two", MemType.FACT)
    s.add("pref one", MemType.PREFERENCE)

    stats = s.stats()
    assert stats["total"] == 3
    assert stats["by_type"]["fact"] == 2
    assert stats["by_type"]["preference"] == 1


def test_namespaces_are_isolated(tmp_path, monkeypatch):
    a = _store(tmp_path, monkeypatch, ns="alice")
    b = _store(tmp_path, monkeypatch, ns="bob")
    a.add("alice's fact")

    assert len(a.entries) == 1
    assert len(b.entries) == 0


def test_enforce_retention_removes_old_low_importance_entries(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    old = s.add("stale fact", importance=3)
    old.created = (datetime.now() - timedelta(days=400)).isoformat()
    s.save()

    result = s.enforce_retention(max_age_days=365)
    assert result["removed_age"] == 1
    assert len(s.entries) == 0


def test_enforce_retention_protects_high_importance_entries(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    important = s.add("critical fact", importance=10)
    important.created = (datetime.now() - timedelta(days=400)).isoformat()
    s.save()

    result = s.enforce_retention(max_age_days=365, protect_above=9)
    assert result["removed_age"] == 0
    assert len(s.entries) == 1


def test_enforce_retention_caps_entry_count(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    for i in range(5):
        s.add(f"fact {i}", importance=1)

    result = s.enforce_retention(max_age_days=3650, max_entries=2)
    assert result["removed_cap"] == 3
    assert len(s.entries) == 2


def test_enforce_retention_never_uses_dropped_prot_variable(tmp_path, monkeypatch):
    """Regression test for the dead-code fix in enforce_retention() —
    a `prot` local variable was computed but never used in the
    original (confirmed via pyflakes on the untouched source); removing
    it must not change behavior. This test exercises the exact code
    path where `prot` used to be assigned (max_entries cap triggered
    with a mix of protected and unprotected entries) and checks the
    protected one survives."""
    s = _store(tmp_path, monkeypatch)
    protected = s.add("keep me", importance=10)
    for i in range(5):
        s.add(f"disposable {i}", importance=1)

    s.enforce_retention(max_age_days=3650, max_entries=2, protect_above=9)
    remaining_ids = {e.mid for e in s.entries}
    assert protected.mid in remaining_ids

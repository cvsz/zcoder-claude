"""tests/unit/domain/test_memory.py

Covers domain/memory.py — pure MemType/MemEntry, extracted 2026-08-18
(Phase C, Context #5).
"""

from domain.memory import MemType, MemEntry


def test_mem_entry_roundtrip():
    e = MemEntry(content="likes tea", mtype=MemType.PREFERENCE, tags=["food"], importance=7)
    d = e.to_dict()
    e2 = MemEntry.from_dict(d)
    assert e2.content == "likes tea"
    assert e2.mtype == MemType.PREFERENCE
    assert e2.tags == ["food"]
    assert e2.importance == 7


def test_mem_entry_default_type_is_fact():
    e = MemEntry()
    assert e.mtype == MemType.FACT


def test_mem_type_values():
    assert MemType.FACT.value == "fact"
    assert MemType.PREFERENCE.value == "preference"
    assert MemType.EVENT.value == "event"
    assert MemType.TASK.value == "task"


def test_mem_entry_from_dict_defaults_missing_mtype_to_fact():
    e = MemEntry.from_dict({"mid": "x", "content": "hi"})
    assert e.mtype == MemType.FACT

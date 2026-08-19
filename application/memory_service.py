"""
application/memory_service.py — use-case layer for the Memory bounded
context
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Orchestrates infrastructure/local_storage/memory_store.py — no I/O of
its own, no print(). Extracted 2026-08-18. Original cmd_* bodies were
already thin (one MemoryStore call + prints), so these ops are thin too.
"""

from typing import Dict, List, Optional

from infrastructure.local_storage.memory_store import MemoryStore
from domain.memory import MemEntry, MemType


def add_memory(content: str, mtype: str = "fact", tags: Optional[List[str]] = None,
               importance: int = 5, ns: str = "default") -> MemEntry:
    store = MemoryStore(ns)
    return store.add(content, MemType(mtype), tags=tags or [], importance=importance)


def recall_memories(query: str, ns: str = "default", limit: int = 6) -> List[MemEntry]:
    store = MemoryStore(ns)
    return store.recall(query, limit)


def forget_memory(mid: str, ns: str = "default") -> bool:
    store = MemoryStore(ns)
    return store.forget(mid)


def get_stats(ns: str = "default") -> Dict:
    store = MemoryStore(ns)
    return store.stats()


def apply_retention(ns: str = "default", max_age_days: int = 365,
                     max_entries: int = 2000) -> tuple:
    """Returns (removal_counts_dict, remaining_entry_count)."""
    store = MemoryStore(ns)
    result = store.enforce_retention(max_age_days=max_age_days, max_entries=max_entries)
    return result, len(store.entries)

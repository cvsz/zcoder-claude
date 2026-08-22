"""
infrastructure/local_storage/memory_store.py — MemoryStore, the
namespaced, disk-backed cross-session memory store
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Extracted 2026-08-18 from claude_memory.py's MemoryStore class,
unmodified in behavior. Kept as a single class rather than split
method-by-method between domain/ and infrastructure/ — same reasoning
as CodeSession/PptxSession/ExcelSession: _load()/save() touch disk,
while recall()'s scoring, context_block(), and stats() are pure logic,
but they all operate on the same `self.entries` state and this
project has no precedent for splitting one class's methods across
layers.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from domain.memory import MemEntry, MemType

MEMORY_DIR = Path.home() / ".zcoder" / "memory"


class MemoryStore:
    def __init__(self, ns: str = "default"):
        self.ns = ns
        self.entries: list[MemEntry] = []
        self._load()

    def _path(self) -> Path:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        return MEMORY_DIR / f"{self.ns}.json"

    def _load(self):
        p = self._path()
        if p.exists():
            self.entries = [MemEntry.from_dict(d) for d in json.loads(p.read_text())]

    def save(self):
        self._path().write_text(json.dumps([e.to_dict() for e in self.entries], indent=2))

    def add(
        self,
        content: str,
        mtype: MemType = MemType.FACT,
        tags: list[str] | None = None,
        importance: int = 5,
    ) -> MemEntry:
        e = MemEntry(content=content, mtype=mtype, tags=tags or [], importance=importance)
        self.entries.append(e)
        self.save()
        return e

    def recall(self, query: str, limit: int = 6) -> list[MemEntry]:
        words = set(query.lower().split())
        scored = []
        for e in self.entries:
            overlap = len(words & set(e.content.lower().split()))
            tag_hit = sum(1 for t in e.tags if t.lower() in query.lower())
            score = overlap + tag_hit * 2 + e.importance * 0.1
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = [e for _, e in scored[:limit]]
        for e in out:
            e.accessed = datetime.now().isoformat()
        if out:
            self.save()
        return out

    def forget(self, mid: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.mid != mid]
        if len(self.entries) < before:
            self.save()
            return True
        return False

    def context_block(self, query: str, limit: int = 5) -> str:
        hits = self.recall(query, limit)
        if not hits:
            return ""
        lines = ["## Memory Context"]
        for h in hits:
            lines.append(f"- [{h.mtype.value}] {h.content}")
        return "\n".join(lines)

    def stats(self) -> dict[str, Any]:
        by_type = {}
        for t in MemType:
            by_type[t.value] = sum(1 for e in self.entries if e.mtype == t)
        return {"total": len(self.entries), "by_type": by_type, "namespace": self.ns}

    def enforce_retention(
        self, max_age_days: int = 365, max_entries: int = 2000, protect_above: int = 9
    ) -> dict[str, int]:
        now = datetime.now()
        removed_age = 0
        removed_cap = 0
        cutoff = now - timedelta(days=max_age_days)
        kept = [
            e
            for e in self.entries
            if e.importance >= protect_above or datetime.fromisoformat(e.created) >= cutoff
        ]
        removed_age = len(self.entries) - len(kept)
        self.entries = kept
        if len(self.entries) > max_entries:
            unprot = sorted(
                [e for e in self.entries if e.importance < protect_above], key=lambda e: e.importance
            )
            drop = max(0, len(self.entries) - max_entries)
            drop_ids = {e.mid for e in unprot[:drop]}
            removed_cap = len(drop_ids)
            self.entries = [e for e in self.entries if e.mid not in drop_ids]
        self.save()
        return {"removed_age": removed_age, "removed_cap": removed_cap}

"""
domain/memory.py — Persistent cross-session memory domain layer
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Pure data for the Memory bounded context — MemType and MemEntry
(to_dict/from_dict only, no I/O). Extracted 2026-08-18 from
claude_memory.py.

MemoryStore itself is NOT here — same reasoning as CodeSession/
PptxSession/ExcelSession: its methods mix pure logic (recall()'s
keyword+importance scoring, context_block(), stats()) with disk I/O
(_load()/save()), all operating on the same `self.entries` state, so
it stays as one class in infrastructure/local_storage/memory_store.py.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemType(Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    EVENT = "event"
    TASK = "task"


@dataclass
class MemEntry:
    mid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    mtype: MemType = MemType.FACT
    tags: list[str] = field(default_factory=list)
    importance: int = 5  # 1–10; 10 = never auto-deleted
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    accessed: str | None = None

    def to_dict(self):
        return {
            "mid": self.mid,
            "content": self.content,
            "mtype": self.mtype.value,
            "tags": self.tags,
            "importance": self.importance,
            "created": self.created,
            "accessed": self.accessed,
        }

    @staticmethod
    def from_dict(d) -> MemEntry:
        e = MemEntry()
        e.mid = d["mid"]
        e.content = d["content"]
        e.mtype = MemType(d.get("mtype", "fact"))
        e.tags = d.get("tags", [])
        e.importance = d.get("importance", 5)
        e.created = d.get("created", datetime.now().isoformat())
        e.accessed = d.get("accessed")
        return e

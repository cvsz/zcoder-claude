"""
domain/sessions.py — Persistent sessions domain layer
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Pure data for the Sessions bounded context — Turn/Session/Checkpoint
dataclasses (to_dict/from_dict/add_turn/recap are all in-memory only,
no I/O) plus the SKIP_DIRS constant used by away_summary's directory
walk. No I/O, no print(). Extracted 2026-08-18 from claude_sessions.py.
"""

import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}


@dataclass
class Turn:
    role:    str
    content: str
    ts:      str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self): return {"role": self.role, "content": self.content, "ts": self.ts}

    @staticmethod
    def from_dict(d): return Turn(role=d["role"], content=d["content"], ts=d.get("ts",""))


@dataclass
class Session:
    sid:     str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    mode:    str = "interactive"
    title:   Optional[str] = None
    model:   str = "claude-sonnet-5"
    persona: Optional[str] = None
    turns:   List[Turn] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_turn(self, role: str, content: str):
        self.turns.append(Turn(role=role, content=content))
        self.updated = datetime.now().isoformat()

    def to_dict(self):
        return {"sid": self.sid, "mode": self.mode, "title": self.title,
                "model": self.model, "persona": self.persona,
                "turns": [t.to_dict() for t in self.turns],
                "created": self.created, "updated": self.updated}

    @staticmethod
    def from_dict(d):
        s = Session(sid=d["sid"], mode=d.get("mode","interactive"),
                    title=d.get("title"), model=d.get("model","claude-sonnet-5"),
                    persona=d.get("persona"), created=d.get("created",""),
                    updated=d.get("updated",""))
        s.turns = [Turn.from_dict(t) for t in d.get("turns", [])]
        return s

    def recap(self, n: int = 3) -> str:
        if not self.turns: return f"[{self.sid}] empty"
        lines = [f"Session [{self.sid}] — {len(self.turns)} turns, {self.mode}"]
        for t in self.turns[-n:]:
            preview = t.content[:100].replace("\n"," ")
            lines.append(f"  {t.role}: {preview}{'…' if len(t.content)>100 else ''}")
        return "\n".join(lines)


@dataclass
class Checkpoint:
    cpid:    str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sid:     str = ""
    label:   str = ""
    n_turns: int = 0
    snap:    List[Dict] = field(default_factory=list)
    ts:      str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {"cpid": self.cpid, "sid": self.sid, "label": self.label,
                "n_turns": self.n_turns, "snap": self.snap, "ts": self.ts}

    @staticmethod
    def from_dict(d):
        cp = Checkpoint()
        cp.cpid=d["cpid"]; cp.sid=d["sid"]; cp.label=d.get("label","")
        cp.n_turns=d.get("n_turns",0); cp.snap=d.get("snap",[]); cp.ts=d.get("ts","")
        return cp

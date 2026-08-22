"""
domain/projects.py — Feature Projects subsystem domain layer
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Pure data: project lifecycle status constants and the Task record.
No I/O of any kind. Extracted 2026-08-22 from projects.py.
"""

import uuid
from datetime import UTC, datetime


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ProjectStatus:
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"
    ARCHIVED = "archived"


class Task:
    def __init__(
        self,
        title: str,
        description: str = "",
        agent: str = "",
        priority: str = "medium",
        task_id: str | None = None,
    ):
        self.id = task_id or str(uuid.uuid4())[:8]
        self.title = title
        self.description = description
        self.agent = agent  # which agent handles this
        self.priority = priority  # low / medium / high / critical
        self.status = "todo"  # todo / in_progress / done / blocked
        self.created_at = _now()
        self.updated_at = _now()
        self.result = ""

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: dict) -> Task:
        t = cls.__new__(cls)
        t.__dict__.update(d)
        return t

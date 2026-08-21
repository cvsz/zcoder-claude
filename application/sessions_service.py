"""
application/sessions_service.py — use-case layer for the Sessions
bounded context
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Orchestrates infrastructure/local_storage/sessions_store.py — no I/O of
its own, no print(). Extracted 2026-08-18. Original cmd_* bodies were
already thin (one store call + prints), so these ops are thin too.
"""


from domain.sessions import Checkpoint, Session
from infrastructure.local_storage import sessions_store as store


def list_all_sessions() -> list[Session]:
    return store.list_sessions()


def get_session(sid: str) -> Session | None:
    return store.load_session(sid)


def get_checkpoints(sid: str) -> list[Checkpoint]:
    return store.list_checkpoints(sid)


def get_away_summary(sid: str, cwd: str = ".") -> str | None:
    """Returns None if the session isn't found (caller prints the
    "Session not found" message), else the away-summary text."""
    s = store.load_session(sid)
    if not s:
        return None
    return store.away_summary(cwd, s.updated)

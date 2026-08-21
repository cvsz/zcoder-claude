"""tests/unit/domain/test_sessions.py

Covers domain/sessions.py — pure Turn/Session/Checkpoint dataclasses,
extracted 2026-08-18 (Phase C, Context #5).
"""

from domain.sessions import SKIP_DIRS, Checkpoint, Session, Turn


def test_turn_roundtrip():
    t = Turn(role="user", content="hi")
    d = t.to_dict()
    t2 = Turn.from_dict(d)
    assert t2.role == "user"
    assert t2.content == "hi"
    assert t2.ts == t.ts


def test_session_add_turn_updates_timestamp():
    s = Session()
    original_updated = s.updated
    s.add_turn("user", "hello")
    assert len(s.turns) == 1
    assert s.turns[0].content == "hello"
    assert s.updated >= original_updated


def test_session_roundtrip():
    s = Session(mode="batch", title="my session", model="claude-opus-4-8")
    s.add_turn("user", "hi")
    s.add_turn("assistant", "hello there")
    d = s.to_dict()
    s2 = Session.from_dict(d)
    assert s2.sid == s.sid
    assert s2.mode == "batch"
    assert s2.title == "my session"
    assert len(s2.turns) == 2


def test_session_recap_empty():
    s = Session()
    assert "empty" in s.recap()


def test_session_recap_truncates_long_content():
    s = Session()
    s.add_turn("user", "x" * 200)
    recap = s.recap(n=1)
    assert "…" in recap


def test_checkpoint_roundtrip():
    cp = Checkpoint(
        sid="abc123",
        label="before refactor",
        n_turns=3,
        snap=[{"role": "user", "content": "hi", "ts": "now"}],
    )
    d = cp.to_dict()
    cp2 = Checkpoint.from_dict(d)
    assert cp2.sid == "abc123"
    assert cp2.label == "before refactor"
    assert cp2.n_turns == 3
    assert cp2.snap == cp.snap


def test_skip_dirs_contains_common_ignore_patterns():
    for d in (".git", "node_modules", "__pycache__", "venv"):
        assert d in SKIP_DIRS

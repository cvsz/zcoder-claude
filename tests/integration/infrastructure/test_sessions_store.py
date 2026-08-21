"""tests/test_sessions_store.py

Covers infrastructure/local_storage/sessions_store.py, extracted
2026-08-18 (Phase C, Context #5) from claude_sessions.py. Uses real
disk I/O against tmp_path — no mocks.
"""

import infrastructure.local_storage.sessions_store as store
from domain.sessions import Session


def test_save_and_load_session_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SESSIONS_DIR", tmp_path)
    s = Session(mode="interactive", title="test")
    s.add_turn("user", "hello")
    store.save_session(s)

    loaded = store.load_session(s.sid)
    assert loaded is not None
    assert loaded.sid == s.sid
    assert loaded.title == "test"
    assert len(loaded.turns) == 1


def test_load_session_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SESSIONS_DIR", tmp_path)
    assert store.load_session("nonexistent") is None


def test_list_sessions_sorted_by_updated_desc(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SESSIONS_DIR", tmp_path)
    s1 = Session()
    s1.updated = "2026-01-01T00:00:00"
    s2 = Session()
    s2.updated = "2026-06-01T00:00:00"
    store.save_session(s1)
    store.save_session(s2)

    result = store.list_sessions()
    assert [s.sid for s in result] == [s2.sid, s1.sid]


def test_list_sessions_filters_by_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SESSIONS_DIR", tmp_path)
    s1 = Session(mode="interactive")
    s2 = Session(mode="batch")
    store.save_session(s1)
    store.save_session(s2)

    result = store.list_sessions(mode="batch")
    assert [s.sid for s in result] == [s2.sid]


def test_list_sessions_skips_unparseable_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SESSIONS_DIR", tmp_path)
    (tmp_path / "bad.json").write_text("{not valid json")
    s = Session()
    store.save_session(s)

    result = store.list_sessions()
    assert len(result) == 1
    assert result[0].sid == s.sid


def test_latest_session_returns_most_recently_updated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SESSIONS_DIR", tmp_path)
    s1 = Session()
    s1.updated = "2026-01-01T00:00:00"
    s2 = Session()
    s2.updated = "2026-06-01T00:00:00"
    store.save_session(s1)
    store.save_session(s2)

    assert store.latest_session().sid == s2.sid


def test_latest_session_no_sessions_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SESSIONS_DIR", tmp_path)
    assert store.latest_session() is None


def test_capture_and_list_checkpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "CHECKPOINTS_DIR", tmp_path)
    s = Session()
    s.add_turn("user", "hi")
    cp = store.capture_checkpoint(s, "before edit")

    checkpoints = store.list_checkpoints(s.sid)
    assert len(checkpoints) == 1
    assert checkpoints[0].cpid == cp.cpid
    assert checkpoints[0].label == "before edit"


def test_rewind_to_checkpoint_restores_turns(tmp_path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    checkpoints_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(store, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(store, "CHECKPOINTS_DIR", checkpoints_dir)

    s = Session()
    s.add_turn("user", "turn 1")
    cp = store.capture_checkpoint(s, "checkpoint 1")
    s.add_turn("user", "turn 2")
    assert len(s.turns) == 2

    restored = store.rewind_to_checkpoint(s, cp.cpid)
    assert len(restored.turns) == 1
    assert restored.turns[0].content == "turn 1"


def test_rewind_to_missing_checkpoint_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "CHECKPOINTS_DIR", tmp_path)
    s = Session()
    try:
        store.rewind_to_checkpoint(s, "nonexistent")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "not found" in str(e)


def test_rewind_wrong_session_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "CHECKPOINTS_DIR", tmp_path)
    s1 = Session()
    s1.add_turn("user", "hi")
    cp = store.capture_checkpoint(s1, "cp")

    s2 = Session()
    try:
        store.rewind_to_checkpoint(s2, cp.cpid)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "different session" in str(e)


def test_away_summary_no_changes(tmp_path):
    result = store.away_summary(str(tmp_path), "2026-01-01T00:00:00")
    assert "No changes" in result


def test_away_summary_detects_modified_file(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    since = "2020-01-01T00:00:00"
    result = store.away_summary(str(tmp_path), since)
    assert "modified" in result
    assert "notes.txt" in result

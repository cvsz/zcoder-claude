"""tests/unit/application/test_sessions_service.py

Covers application/sessions_service.py, extracted 2026-08-18 (Phase C,
Context #5). Fake store module functions substituted in.
"""

import application.sessions_service as service
from domain.sessions import Session


def test_list_all_sessions_delegates(monkeypatch):
    fake_sessions = [Session(), Session()]
    monkeypatch.setattr(service.store, "list_sessions", lambda: fake_sessions)
    assert service.list_all_sessions() == fake_sessions


def test_get_session_delegates(monkeypatch):
    s = Session()
    monkeypatch.setattr(service.store, "load_session", lambda sid: s if sid == "abc" else None)
    assert service.get_session("abc") is s
    assert service.get_session("missing") is None


def test_get_checkpoints_delegates(monkeypatch):
    monkeypatch.setattr(service.store, "list_checkpoints", lambda sid: [f"cp-{sid}"])
    assert service.get_checkpoints("abc") == ["cp-abc"]


def test_get_away_summary_returns_none_for_missing_session(monkeypatch):
    monkeypatch.setattr(service.store, "load_session", lambda sid: None)
    assert service.get_away_summary("missing") is None


def test_get_away_summary_delegates_for_found_session(monkeypatch):
    s = Session()
    s.updated = "2026-01-01T00:00:00"
    monkeypatch.setattr(service.store, "load_session", lambda sid: s)
    captured = {}

    def fake_away_summary(cwd, since_iso):
        captured["cwd"] = cwd
        captured["since"] = since_iso
        return "summary text"

    monkeypatch.setattr(service.store, "away_summary", fake_away_summary)
    result = service.get_away_summary(s.sid, cwd="/some/project")
    assert result == "summary text"
    assert captured == {"cwd": "/some/project", "since": "2026-01-01T00:00:00"}

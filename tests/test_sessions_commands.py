"""tests/test_sessions_commands.py

Covers interfaces/cli/commands/sessions_commands.py, extracted
2026-08-18 (Phase C, Context #5). Uses capsys to verify actual printed
output.
"""

import interfaces.cli.commands.sessions_commands as cmds
from domain.sessions import Session


def test_cmd_sessions_list_empty(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "list_all_sessions", lambda: [])
    cmds.cmd_sessions_list()
    assert "No saved sessions." in capsys.readouterr().out


def test_cmd_sessions_list_shows_sessions(monkeypatch, capsys):
    s = Session(mode="batch", title="my title")
    s.add_turn("user", "hi")
    monkeypatch.setattr(cmds.service, "list_all_sessions", lambda: [s])
    cmds.cmd_sessions_list()
    out = capsys.readouterr().out
    assert s.sid in out
    assert "batch" in out
    assert "my title" in out


def test_cmd_session_show_not_found(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "get_session", lambda sid: None)
    cmds.cmd_session_show("missing")
    assert "Session not found: missing" in capsys.readouterr().out


def test_cmd_session_show_prints_recap(monkeypatch, capsys):
    s = Session()
    s.add_turn("user", "hello there")
    monkeypatch.setattr(cmds.service, "get_session", lambda sid: s)
    cmds.cmd_session_show(s.sid)
    out = capsys.readouterr().out
    assert "hello there" in out


def test_cmd_checkpoint_list_empty(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "get_checkpoints", lambda sid: [])
    cmds.cmd_checkpoint_list("abc")
    assert "No checkpoints for session abc" in capsys.readouterr().out


def test_cmd_away_summary_not_found(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "get_away_summary", lambda sid, cwd: None)
    cmds.cmd_away_summary("missing")
    assert "Session not found: missing" in capsys.readouterr().out


def test_cmd_away_summary_prints_result(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "get_away_summary", lambda sid, cwd: "3 files changed")
    cmds.cmd_away_summary("abc")
    assert "3 files changed" in capsys.readouterr().out

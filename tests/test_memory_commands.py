"""tests/test_memory_commands.py

Covers interfaces/cli/commands/memory_commands.py, extracted
2026-08-18 (Phase C, Context #5). Uses capsys — including a check that
the comma-separated `tags` CLI string is parsed correctly before being
handed to application/memory_service.py.
"""

import interfaces.cli.commands.memory_commands as cmds
from domain.memory import MemEntry, MemType


def test_cmd_memory_add_parses_comma_separated_tags(monkeypatch, capsys):
    captured = {}

    def fake_add_memory(content, mtype, tags, importance, ns):
        captured["tags"] = tags
        return MemEntry(mid="m1", content=content, mtype=MemType.FACT)

    monkeypatch.setattr(cmds.service, "add_memory", fake_add_memory)
    cmds.cmd_memory_add("likes tea", tags=" coffee, tea ,, drinks ")
    assert captured["tags"] == ["coffee", "tea", "drinks"]
    assert "Stored [m1]" in capsys.readouterr().out


def test_cmd_memory_recall_no_hits(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "recall_memories", lambda query, ns, limit: [])
    cmds.cmd_memory_recall("nothing")
    assert "No matching memories." in capsys.readouterr().out


def test_cmd_memory_recall_prints_hits_with_tags(monkeypatch, capsys):
    hit = MemEntry(mid="m1", content="likes tea", mtype=MemType.PREFERENCE, tags=["drink"], importance=6)
    monkeypatch.setattr(cmds.service, "recall_memories", lambda query, ns, limit: [hit])
    cmds.cmd_memory_recall("tea")
    out = capsys.readouterr().out
    assert "likes tea" in out
    assert "tags: drink" in out


def test_cmd_memory_forget_found(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "forget_memory", lambda mid, ns: True)
    cmds.cmd_memory_forget("m1")
    assert "Forgot m1" in capsys.readouterr().out


def test_cmd_memory_forget_not_found(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "forget_memory", lambda mid, ns: False)
    cmds.cmd_memory_forget("missing")
    assert "Not found: missing" in capsys.readouterr().out


def test_cmd_memory_stats_prints_breakdown(monkeypatch, capsys):
    monkeypatch.setattr(
        cmds.service,
        "get_stats",
        lambda ns: {
            "namespace": "default",
            "total": 3,
            "by_type": {"fact": 2, "task": 1},
        },
    )
    cmds.cmd_memory_stats()
    out = capsys.readouterr().out
    assert "Total: 3" in out
    assert "fact" in out


def test_cmd_memory_retention_prints_summary(monkeypatch, capsys):
    monkeypatch.setattr(
        cmds.service,
        "apply_retention",
        lambda ns, max_age_days, max_entries: ({"removed_age": 2, "removed_cap": 1}, 7),
    )
    cmds.cmd_memory_retention()
    out = capsys.readouterr().out
    assert "removed 2 by age" in out
    assert "1 by cap" in out
    assert "7 remain" in out

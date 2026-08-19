"""tests/test_cache_commands.py

Covers interfaces/cli/commands/cache_commands.py, extracted 2026-08-18
(Phase C, Context #5) — particularly _print_cache_stats(), which used
to be a method on CachingCoder itself (see infrastructure/anthropic_api/
cache_gateway.py's module docstring for why it moved), and
cmd_cache_warm's file-read-error-then-success print ordering.
"""

import interfaces.cli.commands.cache_commands as cmds
from domain.cache import SystemMessagePlacementError


def test_print_cache_stats_shows_hit_rate(capsys):
    cmds._print_cache_stats({
        "input_tokens": 10, "output_tokens": 5,
        "cache_creation_input_tokens": 20, "cache_read_input_tokens": 70,
        "cache_miss_reason": None,
    })
    out = capsys.readouterr().out
    assert "input tokens:        10" in out
    assert "cache write tokens:  20" in out
    assert "cache read tokens:   70" in out
    assert "70.0%" in out  # 70/(70+20+10)*100


def test_print_cache_stats_shows_dash_when_no_usage(capsys):
    cmds._print_cache_stats({
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        "cache_miss_reason": None,
    })
    assert "cache hit rate:      —" in capsys.readouterr().out


def test_print_cache_stats_shows_miss_reason_when_present(capsys):
    cmds._print_cache_stats({
        "input_tokens": 1, "output_tokens": 1,
        "cache_creation_input_tokens": 1, "cache_read_input_tokens": 0,
        "cache_miss_reason": "system_changed",
    })
    out = capsys.readouterr().out
    assert "cache miss reason:   system_changed" in out


def test_cmd_cache_generate_prints_result_and_stats(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "generate", lambda *a, **k: (
        "the answer",
        {"input_tokens": 1, "output_tokens": 1, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": 0, "cache_miss_reason": None},
    ))
    cmds.cmd_cache_generate("hi", "key", "claude-sonnet-5")
    out = capsys.readouterr().out
    assert "the answer" in out
    assert "Cache Stats" in out


def test_cmd_cache_multi_turn_catches_placement_error(monkeypatch, capsys):
    def raise_placement_error(*a, **k):
        raise SystemMessagePlacementError("bad placement")

    monkeypatch.setattr(cmds.service, "multi_turn", raise_placement_error)
    result = cmds.cmd_cache_multi_turn(["a", "b"], "key", "claude-opus-4-8",
                                        mid_system="x")
    assert result == []
    assert "bad placement" in capsys.readouterr().out


def test_cmd_cache_warm_prints_warnings_before_success(monkeypatch, capsys):
    monkeypatch.setattr(cmds.service, "warm", lambda *a, **k: (
        {"cache_creation_input_tokens": 99},
        {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 99,
         "cache_read_input_tokens": 0, "cache_miss_reason": None},
        [("missing.txt", "No such file")],
    ))
    cmds.cmd_cache_warm("key", "claude-sonnet-5", doc_files=["missing.txt"])
    out = capsys.readouterr().out
    warn_idx = out.index("Cannot read missing.txt")
    success_idx = out.index("Cache warmed")
    assert warn_idx < success_idx
    assert "99 tokens" in out

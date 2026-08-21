"""tests/test_batch_commands.py

Covers interfaces/cli/commands/batch_commands.py — specifically the
print()-based on_warning/on_progress callbacks it supplies to
application/batch_service.py, extracted 2026-08-18 (Phase C,
Context #4). Uses capsys rather than a fake service — the whole point
of this file is to verify actual printed output/formatting.
"""

import interfaces.cli.commands.batch_commands as cmds


def test_on_warning_prints_yellow_warning(capsys):
    cmds._on_warning("model isn't eligible")
    out = capsys.readouterr().out
    assert "model isn't eligible" in out
    assert "\033[93m" in out


def test_on_progress_prints_carriage_return_line(capsys):
    cmds._on_progress("batch_123", {"status": "in_progress", "request_counts": {"a": 1}}, 30)
    out = capsys.readouterr().out
    assert out.startswith("\r")
    assert "batch_123" in out
    assert "in_progress" in out
    assert "waited 30s" in out
    assert not out.endswith("\n")  # end="" — no trailing newline, matches original


def test_cmd_batch_generate_with_wait_prints_trailing_newline_after_progress(monkeypatch, capsys):
    """Original wait() always printed exactly one bare newline right
    before returning, regardless of which branch (ended vs. max_wait)
    it took. Reproduced here as an unconditional print() right after
    service.wait_for_batch(...) — verify it's actually there."""
    import application.batch_service as service

    monkeypatch.setattr(service, "generate_and_submit", lambda *a, **k: "batch_xyz")
    monkeypatch.setattr(
        service,
        "wait_for_batch",
        lambda batch_id, api_key, on_progress: on_progress(batch_id, {"status": "ended"}, 15),
    )
    monkeypatch.setattr(
        service,
        "get_results",
        lambda *a, **k: [
            {"custom_id": "r1", "type": "succeeded", "text": "done"},
        ],
    )

    cmds.cmd_batch_generate("write tests", 1, "key", "claude-sonnet-5", wait=True)

    out = capsys.readouterr().out
    # the \r progress line, immediately followed by a bare newline before
    # "── r1 ──" — i.e. the progress line's carriage-return trick doesn't
    # bleed into the results output below it.
    assert "\r\033[94mℹ [batch_xyz]" in out
    assert "── r1 ──" in out
    progress_idx = out.index("waited 15s")
    results_idx = out.index("── r1 ──")
    between = out[progress_idx:results_idx]
    assert "\n" in between


def test_cmd_batch_list_empty_prints_message(monkeypatch, capsys):
    import application.batch_service as service

    monkeypatch.setattr(service, "list_batches", lambda api_key: [])
    cmds.cmd_batch_list("key")
    assert "No batches found." in capsys.readouterr().out


def test_cmd_batch_status_prints_all_fields(monkeypatch, capsys):
    import application.batch_service as service

    monkeypatch.setattr(
        service,
        "get_status",
        lambda batch_id, api_key: {
            "id": "batch_123",
            "status": "ended",
            "request_counts": {"succeeded": 5},
            "created_at": "2026-08-18T00:00:00Z",
            "expires_at": "2026-08-25T00:00:00Z",
        },
    )
    cmds.cmd_batch_status("batch_123", "key")
    out = capsys.readouterr().out
    assert "batch_123" in out
    assert "ended" in out
    assert "2026-08-18T00:00:00" in out

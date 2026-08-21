"""tests/test_pptx_deck_store.py

Covers infrastructure/local_storage/pptx_deck_store.py's PptxSession,
extracted 2026-08-18 (Phase C, Context #4) from claude_powerpoint.py.
Uses the real python-pptx library against tmp_path — no mocks — the
same style as tests/test_claude_code_context_editing.py's approach for
disk-touching classes: verify the actual on-disk artifact, not just
in-memory state.
"""

import pytest

from infrastructure.local_storage.pptx_deck_store import PptxSession


def test_new_session_has_no_slides():
    s = PptxSession()
    assert s.slides == []
    assert s.summary() == "(no slides yet)"


def test_apply_code_add_slide():
    s = PptxSession()
    ok, msg = s.apply_code('add_slide("Intro", bullets=["point one", "point two"])')
    assert ok is True
    assert msg == "applied"
    assert len(s.slides) == 1
    assert s.slides[0]["title"] == "Intro"
    assert s.slides[0]["bullets"] == ["point one", "point two"]


def test_apply_code_denylist_blocks_dangerous_code():
    s = PptxSession()
    ok, msg = s.apply_code('import os\nadd_slide("x")')
    assert ok is False
    assert "blocked" in msg
    assert len(s.slides) == 0


def test_apply_code_rolls_back_on_exception():
    s = PptxSession()
    s.apply_code('add_slide("first")')
    ok, msg = s.apply_code("undefined_function_call()")
    assert ok is False
    assert "ERROR" in msg
    # rollback: still just the one slide from before the failed turn
    assert len(s.slides) == 1
    assert s.slides[0]["title"] == "first"


def test_undo_reverts_to_previous_snapshot():
    s = PptxSession()
    s.apply_code('add_slide("first")')
    s.apply_code('add_slide("second")')
    assert len(s.slides) == 2
    assert s.undo() is True
    assert len(s.slides) == 1
    assert s.slides[0]["title"] == "first"


def test_undo_with_no_history_returns_false():
    s = PptxSession()
    assert s.undo() is False


def test_save_and_reload_roundtrip(tmp_path):
    s = PptxSession()
    s.apply_code('add_slide("Welcome", bullets=["hello", "world"])')
    out = tmp_path / "deck.pptx"
    s.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0

    reloaded = PptxSession(str(out))
    assert len(reloaded.slides) == 1
    assert reloaded.slides[0]["title"] == "Welcome"
    assert "hello" in reloaded.slides[0]["bullets"]


def test_save_with_table_and_chart(tmp_path):
    s = PptxSession()
    s.apply_code(
        'add_slide("Data", table={"headers": ["A", "B"], "rows": [[1, 2], [3, 4]]}, '
        'chart={"type": "bar", "categories": ["Q1", "Q2"], "series": {"Revenue": [10, 20]}})'
    )
    out = tmp_path / "deck_with_chart.pptx"
    s.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0


def test_summary_includes_table_and_chart_markers():
    s = PptxSession()
    s.apply_code(
        'add_slide("Data", table={"headers": ["A"], "rows": [[1]]}, '
        'chart={"type": "pie", "categories": ["X"], "series": {"S": [1]}})'
    )
    summary = s.summary()
    assert "table 1x1" in summary
    assert "pie chart" in summary


def test_missing_python_pptx_raises_importerror(monkeypatch):
    import infrastructure.local_storage.pptx_deck_store as store

    monkeypatch.setattr(store, "Presentation", None)
    with pytest.raises(ImportError):
        store.PptxSession()

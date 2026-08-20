"""tests/test_excel_workbook_store.py

Covers infrastructure/local_storage/excel_workbook_store.py's
ExcelSession, extracted 2026-08-18 (Phase C, Context #4) from
claude_excel.py. Uses the real pandas/openpyxl libraries against
tmp_path — no mocks, same style as tests/test_pptx_deck_store.py.
"""

import pytest

from infrastructure.local_storage.excel_workbook_store import ExcelSession


def test_new_session_has_default_empty_sheet():
    s = ExcelSession()
    assert list(s.sheets.keys()) == ["Sheet1"]
    assert s.sheets["Sheet1"].empty


def test_apply_code_mutates_sheet():
    s = ExcelSession()
    ok, msg = s.apply_code('sheets["Sheet1"]["x"] = [1, 2, 3]')
    assert ok is True
    assert msg == "applied"
    assert list(s.sheets["Sheet1"]["x"]) == [1, 2, 3]


def test_apply_code_denylist_blocks_dangerous_code():
    s = ExcelSession()
    ok, msg = s.apply_code('import os\nsheets["Sheet1"]["x"] = [1]')
    assert ok is False
    assert "blocked" in msg
    assert s.sheets["Sheet1"].empty


def test_apply_code_rolls_back_on_exception():
    s = ExcelSession()
    s.apply_code('sheets["Sheet1"]["x"] = [1, 2, 3]')
    ok, msg = s.apply_code('sheets["Sheet1"]["y"] = undefined_name')
    assert ok is False
    assert "ERROR" in msg
    # rollback: "x" column from before the failed turn still there, no "y"
    assert "x" in s.sheets["Sheet1"].columns
    assert "y" not in s.sheets["Sheet1"].columns


def test_undo_reverts_to_previous_snapshot():
    s = ExcelSession()
    s.apply_code('sheets["Sheet1"]["x"] = [1]')
    s.apply_code('sheets["Sheet1"]["y"] = [2]')
    assert "y" in s.sheets["Sheet1"].columns
    assert s.undo() is True
    assert "y" not in s.sheets["Sheet1"].columns
    assert "x" in s.sheets["Sheet1"].columns


def test_undo_with_no_history_returns_false():
    s = ExcelSession()
    assert s.undo() is False


def test_save_and_reload_roundtrip(tmp_path):
    s = ExcelSession()
    s.apply_code('sheets["Sheet1"]["x"] = [1, 2, 3]')
    out = tmp_path / "wb.xlsx"
    s.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0

    reloaded = ExcelSession(str(out))
    assert list(reloaded.sheets["Sheet1"]["x"]) == [1, 2, 3]


def test_load_from_csv(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n")
    s = ExcelSession(str(csv_path))
    assert list(s.sheets["Sheet1"]["a"]) == [1, 3]
    assert list(s.sheets["Sheet1"]["b"]) == [2, 4]


def test_load_specific_sheet_from_multi_sheet_workbook(tmp_path):
    import pandas as pd
    out = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(str(out), engine="openpyxl") as writer:
        pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({"y": [2]}).to_excel(writer, sheet_name="Second", index=False)

    s = ExcelSession(str(out), sheet_name="Second")
    assert list(s.sheets.keys()) == ["Second"]
    assert list(s.sheets["Second"]["y"]) == [2]


def test_load_missing_sheet_name_raises_value_error(tmp_path):
    import pandas as pd
    out = tmp_path / "single.xlsx"
    pd.DataFrame({"x": [1]}).to_excel(str(out), sheet_name="Only", index=False)

    with pytest.raises(ValueError):
        ExcelSession(str(out), sheet_name="Missing")


def test_add_chart_and_save(tmp_path):
    s = ExcelSession()
    s.apply_code(
        'sheets["Sheet1"]["cat"] = ["a", "b"]\n'
        'sheets["Sheet1"]["val"] = [10, 20]\n'
        'add_chart("Sheet1", "bar", "My Chart", "cat", ["val"])'
    )
    out = tmp_path / "chart.xlsx"
    s.save(str(out))
    assert out.exists()
    assert out.stat().st_size > 0
    # pending charts flushed after save
    assert s._pending_charts == []


def test_summary_includes_shape_and_columns():
    s = ExcelSession()
    s.apply_code('sheets["Sheet1"]["x"] = [1, 2]')
    summary = s.summary()
    assert "2 rows x 1 cols" in summary
    assert "x" in summary


def test_missing_pandas_raises_importerror(monkeypatch):
    import infrastructure.local_storage.excel_workbook_store as store
    monkeypatch.setattr(store, "pd", None)
    with pytest.raises(ImportError):
        store.ExcelSession()

"""tests/unit/domain/test_excel.py

Covers domain/excel.py — pure constants for the Excel chat bounded
context, extracted 2026-08-18 (Phase C, Context #4).
"""

from domain.excel import _CODE_BLOCK, _DENYLIST, HELP_TEXT, SYSTEM_PROMPT


def test_code_block_extracts_python_fence():
    reply = 'Sure:\n```python\nsheets["Sheet1"] = sheets["Sheet1"].dropna()\n```\n'
    match = _CODE_BLOCK.search(reply)
    assert match is not None
    assert "dropna()" in match.group(1)


def test_code_block_no_match_for_plain_text():
    assert _CODE_BLOCK.search("just some prose, no fences here") is None


def test_denylist_contains_dangerous_constructs():
    for bad in ("import os", "eval(", "exec(", "__import__", "subprocess."):
        assert bad in _DENYLIST


def test_help_text_lists_all_slash_commands():
    for cmd in ("/help", "/exit", "/sheets", "/show", "/undo"):
        assert cmd in HELP_TEXT


def test_system_prompt_forbids_unsafe_builtins():
    for forbidden in ("open(", "eval", "exec", "os", "sys", "subprocess"):
        assert forbidden in SYSTEM_PROMPT


def test_system_prompt_mentions_add_chart_helper():
    assert "add_chart(" in SYSTEM_PROMPT

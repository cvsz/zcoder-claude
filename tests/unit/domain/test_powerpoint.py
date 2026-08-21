"""tests/unit/domain/test_powerpoint.py

Covers domain/powerpoint.py — pure constants for the PowerPoint chat
bounded context, extracted 2026-08-18 (Phase C, Context #4).
"""

from domain.powerpoint import _CODE_BLOCK, _DENYLIST, HELP_TEXT, SYSTEM_PROMPT


def test_code_block_extracts_python_fence():
    reply = 'Sure:\n```python\nadd_slide("Hi")\n```\n'
    match = _CODE_BLOCK.search(reply)
    assert match is not None
    assert match.group(1).strip() == 'add_slide("Hi")'


def test_code_block_extracts_bare_fence():
    reply = '```\nadd_slide("Hi")\n```'
    match = _CODE_BLOCK.search(reply)
    assert match is not None
    assert 'add_slide("Hi")' in match.group(1)


def test_code_block_no_match_for_plain_text():
    assert _CODE_BLOCK.search("just some prose, no fences here") is None


def test_denylist_contains_dangerous_constructs():
    for bad in ("import os", "eval(", "exec(", "__import__", "subprocess."):
        assert bad in _DENYLIST


def test_help_text_lists_all_slash_commands():
    for cmd in ("/help", "/exit", "/slides", "/show", "/undo"):
        assert cmd in HELP_TEXT


def test_system_prompt_forbids_unsafe_builtins():
    for forbidden in ("open(", "eval", "exec", "os", "sys", "subprocess"):
        assert forbidden in SYSTEM_PROMPT

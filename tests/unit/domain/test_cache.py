"""tests/unit/domain/test_cache.py

Covers domain/cache.py's cache_control breakpoint helpers, extracted
2026-08-18 (Phase C, Context #5). The rest of domain/cache.py
(MID_SYSTEM_SUPPORTED_MODELS, build_mid_system_message(),
validate_system_message_placement()) is already covered by
tests/test_claude_cache.py, which imports from the claude_cache.py
shim and continues to pass unmodified — see that file for the fuller
placement-rule test matrix.
"""

from domain.cache import add_cache_breakpoint, make_cache_control


def test_make_cache_control_default_is_5m_ephemeral():
    assert make_cache_control() == {"type": "ephemeral"}


def test_make_cache_control_1h_includes_ttl():
    assert make_cache_control("1h") == {"type": "ephemeral", "ttl": 3600}


def test_add_cache_breakpoint_does_not_mutate_original():
    block = {"type": "text", "text": "hello"}
    result = add_cache_breakpoint(block, "5m")
    assert "cache_control" not in block
    assert result["cache_control"] == {"type": "ephemeral"}
    assert result["text"] == "hello"

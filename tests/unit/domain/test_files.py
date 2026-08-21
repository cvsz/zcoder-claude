"""tests/unit/domain/test_files.py

Covers domain/files.py — pure filename-validation logic for the Files
API bounded context, extracted 2026-08-18 (Phase C, Context #4). This
is the project's first domain/ unit test file — prior migrated domain
layers were only covered indirectly through their application-service
tests; this one is simple and self-contained enough to test directly.
"""

from domain.files import BETA_HEADER, MAX_FILE_SIZE_BYTES, _validate_filename


def test_valid_filename_returns_none():
    assert _validate_filename("report.pdf") is None


def test_empty_filename_is_invalid():
    err = _validate_filename("")
    assert err is not None
    assert "1-255 characters" in err


def test_filename_over_255_chars_is_invalid():
    err = _validate_filename("a" * 256)
    assert err is not None
    assert "1-255 characters" in err


def test_filename_at_255_chars_is_valid():
    assert _validate_filename("a" * 255) is None


def test_forbidden_character_reported():
    err = _validate_filename("bad<name>.txt")
    assert err is not None
    assert "forbidden character" in err
    assert "'<'" in err
    assert "'>'" in err


def test_control_character_is_forbidden():
    err = _validate_filename("bad\x01name.txt")
    assert err is not None
    assert "forbidden character" in err


def test_constants_unchanged():
    assert MAX_FILE_SIZE_BYTES == 500 * 1024 * 1024
    assert BETA_HEADER == "files-api-2025-04-14"

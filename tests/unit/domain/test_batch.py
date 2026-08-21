"""tests/unit/domain/test_batch.py

Covers domain/batch.py — pure feature-flag constants for the Messages
Batch API bounded context, extracted 2026-08-18 (Phase C, Context #4).
"""

from domain.batch import OUTPUT_300K_BETA, OUTPUT_300K_MAX_TOKENS, OUTPUT_300K_MODELS


def test_beta_header_unchanged():
    assert OUTPUT_300K_BETA == "output-300k-2026-03-24"


def test_max_tokens_unchanged():
    assert OUTPUT_300K_MAX_TOKENS == 300_000


def test_eligible_models_include_current_generation():
    for model in ("claude-opus-4-8", "claude-sonnet-5"):
        assert model in OUTPUT_300K_MODELS


def test_eligible_models_exclude_ineligible_generation():
    assert "claude-haiku-4-5-20251001" not in OUTPUT_300K_MODELS

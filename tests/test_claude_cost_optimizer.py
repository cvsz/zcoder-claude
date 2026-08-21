"""tests/test_claude_cost_optimizer.py

claude_cost_optimizer.py had zero test coverage before this release-gate
pass (2026-08-14) — flagged in docs/53_release_gate_v1.40.0.md as the
reason a stale Sonnet 5 price ($3/$15 instead of the now-permanent $2/$10)
went undetected. This file covers the pricing table, estimate_cost()'s
surcharge/geo-multiplier logic, and the complexity router, so a future
pricing regression here fails a test instead of shipping silently.
"""

import pytest

from claude_cost_optimizer import (
    INFERENCE_GEO_MULTIPLIER,
    INFERENCE_GEO_SUPPORTED,
    LONG_CONTEXT_SURCHARGE,
    PRICE,
    SONNET5_INTRO_PRICE,
    classify_complexity,
    estimate_cost,
    select_model,
)

# ── pricing table (2026-08-10 release note: $2/$10 is now permanent) ────


def test_sonnet5_price_is_2_10_not_cancelled_3_15():
    assert PRICE["claude-sonnet-5"] == {"in": 2.0, "out": 10.0}


def test_sonnet5_intro_price_alias_matches_standard_price():
    # SONNET5_INTRO_PRICE is kept only for backward compatibility and
    # should always equal the base PRICE entry now that there's no
    # separate promo rate.
    assert SONNET5_INTRO_PRICE == PRICE["claude-sonnet-5"]


def test_estimate_cost_use_intro_pricing_flag_is_a_no_op_for_sonnet5():
    with_intro = estimate_cost("claude-sonnet-5", 1_000_000, 1_000_000, use_intro_pricing=True)
    without_intro = estimate_cost("claude-sonnet-5", 1_000_000, 1_000_000, use_intro_pricing=False)
    assert with_intro == without_intro == pytest.approx(2.0 + 10.0)


def test_estimate_cost_unknown_model_falls_back_to_default():
    cost = estimate_cost("claude-unknown-future-model", 1_000_000, 1_000_000)
    assert cost == pytest.approx(3.0 + 15.0)


# ── long-context surcharge ────────────────────────────────────────────


def test_surcharge_applies_above_threshold():
    model = "claude-sonnet-4-5"
    threshold = LONG_CONTEXT_SURCHARGE[model]["threshold"]
    base = PRICE[model]
    cost = estimate_cost(model, threshold + 1, 1_000_000)
    expected = (threshold + 1) / 1e6 * base["in"] * 2.0 + 1_000_000 / 1e6 * base["out"] * 1.5
    assert cost == pytest.approx(expected)


def test_surcharge_does_not_apply_at_or_below_threshold():
    model = "claude-sonnet-4-5"
    threshold = LONG_CONTEXT_SURCHARGE[model]["threshold"]
    base = PRICE[model]
    cost = estimate_cost(model, threshold, 1_000_000)
    expected = threshold / 1e6 * base["in"] + 1_000_000 / 1e6 * base["out"]
    assert cost == pytest.approx(expected)


def test_surcharge_not_modeled_for_flat_rate_models():
    # Opus 4.8/Sonnet 5 etc. get the full 1M context at flat pricing --
    # deliberately absent from LONG_CONTEXT_SURCHARGE.
    for model in ("claude-opus-4-8", "claude-sonnet-5", "claude-sonnet-4-6"):
        assert model not in LONG_CONTEXT_SURCHARGE


# ── inference_geo pricing multiplier ─────────────────────────────────


def test_inference_geo_us_applies_multiplier_on_supported_model():
    model = "claude-sonnet-5"
    assert model in INFERENCE_GEO_SUPPORTED
    base = estimate_cost(model, 1_000_000, 1_000_000, inference_geo="global")
    geo = estimate_cost(model, 1_000_000, 1_000_000, inference_geo="us")
    assert geo == pytest.approx(base * INFERENCE_GEO_MULTIPLIER)


def test_inference_geo_us_ignored_on_unsupported_model():
    model = "claude-opus-4-5"
    assert model not in INFERENCE_GEO_SUPPORTED
    base = estimate_cost(model, 1_000_000, 1_000_000, inference_geo="global")
    geo = estimate_cost(model, 1_000_000, 1_000_000, inference_geo="us")
    assert geo == base


# ── complexity routing ────────────────────────────────────────────────


def test_classify_complexity_short_prompt_is_low():
    assert classify_complexity("hello there") == "low"


def test_classify_complexity_long_prompt_is_high():
    assert classify_complexity("word " * 900) == "high"


def test_classify_complexity_code_markers_bump_tier():
    prompt = "def a():\nclass B:\nfunction c():\nSELECT * \nCREATE TABLE\nCREATE INDEX"
    assert classify_complexity(prompt) == "high"


def test_select_model_force_overrides_complexity():
    assert select_model("low", force="claude-opus-4-8") == "claude-opus-4-8"


def test_select_model_maps_each_complexity_tier():
    assert select_model("low") == "claude-haiku-4-5-20251001"
    assert select_model("medium") == "claude-sonnet-5"
    assert select_model("high") == "claude-opus-4-8"

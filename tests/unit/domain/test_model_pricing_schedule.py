from datetime import date

from domain.models.catalog import estimate_cost_usd, get_price, sonnet5_price


def test_sonnet5_intro_price_before_cutover():
    assert sonnet5_price(date(2026, 8, 30)) == {"in": 2.0, "out": 10.0}


def test_sonnet5_intro_price_on_august_31():
    assert sonnet5_price(date(2026, 8, 31)) == {"in": 2.0, "out": 10.0}


def test_sonnet5_standard_price_on_september_1():
    assert sonnet5_price(date(2026, 9, 1)) == {"in": 3.0, "out": 15.0}


def test_get_price_accepts_historical_as_of_date():
    assert get_price("claude-sonnet-5", as_of=date(2026, 9, 2)) == {"in": 3.0, "out": 15.0}


def test_estimate_cost_uses_effective_date():
    intro = estimate_cost_usd("claude-sonnet-5", 1_000_000, 1_000_000, as_of=date(2026, 8, 31))
    standard = estimate_cost_usd("claude-sonnet-5", 1_000_000, 1_000_000, as_of=date(2026, 9, 1))
    assert intro == 12.0
    assert standard == 18.0


def test_us_inference_geo_multiplier_composes_with_price_schedule():
    cost = estimate_cost_usd(
        "claude-sonnet-5",
        1_000_000,
        1_000_000,
        inference_geo="us",
        as_of=date(2026, 9, 1),
    )
    assert cost == 19.8

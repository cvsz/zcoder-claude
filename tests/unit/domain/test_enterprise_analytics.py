from decimal import Decimal

import pytest

from domain.enterprise_analytics import build_analytics_query, fractional_cents_to_usd


def test_fractional_cents_to_usd_uses_decimal_exactly():
    assert fractional_cents_to_usd("41280.000000") == Decimal("412.800000")


def test_build_analytics_query_preserves_list_parameters():
    query = build_analytics_query(
        starting_date="2026-08-01",
        ending_date="2026-08-08",
        group_by=["user_id"],
        products=["chat", "claude_code"],
        filters=["rbac_group_id:group_1"],
        page="cursor",
    )
    assert query["group_by[]"] == ["user_id"]
    assert query["products[]"] == ["chat", "claude_code"]
    assert query["filter[]"] == ["rbac_group_id:group_1"]
    assert query["page"] == "cursor"


def test_date_and_range_are_mutually_exclusive():
    with pytest.raises(ValueError):
        build_analytics_query(date="2026-08-01", starting_date="2026-08-01")


def test_ending_date_requires_starting_date():
    with pytest.raises(ValueError):
        build_analytics_query(ending_date="2026-08-08")

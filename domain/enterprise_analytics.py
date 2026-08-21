"""Pure Claude Enterprise Analytics helpers."""

from decimal import Decimal


def fractional_cents_to_usd(amount: str) -> Decimal:
    """Convert Analytics API fractional-cent decimal strings to USD exactly."""
    return Decimal(amount) / Decimal("100")


def build_analytics_query(
    *,
    date=None,
    starting_date=None,
    ending_date=None,
    limit=None,
    page=None,
    group_by=None,
    filters=None,
    products=None,
    order_by=None,
) -> dict:
    if date and (starting_date or ending_date):
        raise ValueError("date cannot be combined with starting_date/ending_date")
    if ending_date and not starting_date:
        raise ValueError("ending_date requires starting_date")
    query = {}
    if date is not None:
        query["date"] = date
    if starting_date is not None:
        query["starting_date"] = starting_date
    if ending_date is not None:
        query["ending_date"] = ending_date
    if limit is not None:
        query["limit"] = limit
    if page is not None:
        query["page"] = page
    if group_by:
        query["group_by[]"] = list(group_by)
    if filters:
        query["filter[]"] = list(filters)
    if products:
        query["products[]"] = list(products)
    if order_by is not None:
        query["order_by"] = order_by
    return query

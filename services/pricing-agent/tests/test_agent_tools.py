from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.agent_tools import (
    calculate_margin,
    get_competitor_prices,
    get_demand_trend,
    get_market_position,
    get_price_history,
    get_product_details,
    update_product_price,
)
from app.enums import DecisionActor
from app.models import CompetitorPrice, OrderEvent, PriceHistory, Product


@pytest.mark.asyncio
async def test_tools_return_expected_data_format(db_session, seeded_product):
    details = await get_product_details(1, session=db_session)
    assert set(details.keys()) == {
        "id",
        "name",
        "category",
        "our_price",
        "cost_price",
        "stock",
        "min_margin_percent",
        "is_active",
    }

    competitors = await get_competitor_prices(1, session=db_session)
    assert isinstance(competitors, list)
    assert competitors[0]["competitor_name"] == "CompA"
    assert {"competitor_name", "price", "last_updated"} <= set(competitors[0].keys())

    market = await get_market_position(1, session=db_session)
    assert {
        "product_id",
        "our_price",
        "cheapest_competitor_price",
        "average_competitor_price",
        "highest_competitor_price",
        "price_gap_to_cheapest_percent",
        "safe_increase_ceiling",
        "has_pricing_headroom",
    } <= set(market.keys())

    trend = await get_demand_trend(1, days=7, session=db_session)
    assert {"total_orders", "avg_daily_orders", "trend", "compared_to_previous_period_percent"} <= set(trend.keys())

    history = await get_price_history(1, days=30, session=db_session)
    assert history
    assert {"old_price", "new_price", "reason", "timestamp"} <= set(history[0].keys())


@pytest.mark.asyncio
async def test_margin_calculation_accuracy(db_session):
    db_session.add(
        Product(
            id=22,
            name="Margin Product",
            category="Home",
            description=None,
            our_price=Decimal("110.00"),
            cost_price=Decimal("60.00"),
            stock_quantity=20,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    await db_session.commit()

    result = await calculate_margin(22, Decimal("125.00"), session=db_session)

    assert result["margin_percent"] == 52.0
    assert result["profit_per_unit"] == Decimal("65.00")
    assert result["passes_min_margin"] is True
    assert result["min_margin_threshold"] == 20.0


@pytest.mark.asyncio
async def test_edge_cases_product_not_found_and_no_competitors(db_session):
    with pytest.raises(ValueError, match="was not found"):
        await get_product_details(999, session=db_session)

    db_session.add(
        Product(
            id=23,
            name="No Competitors",
            category="Books",
            description=None,
            our_price=Decimal("45.00"),
            cost_price=Decimal("25.00"),
            stock_quantity=18,
            min_margin_percent=15.0,
            is_active=True,
        )
    )
    await db_session.commit()

    market = await get_market_position(23, session=db_session)
    assert market["cheapest_competitor_price"] is None
    assert market["average_competitor_price"] is None
    assert market["highest_competitor_price"] is None
    assert market["has_pricing_headroom"] is False


@pytest.mark.asyncio
async def test_update_product_price_respects_margin_threshold(db_session):
    db_session.add(
        Product(
            id=24,
            name="Guardrail Product",
            category="Electronics",
            description=None,
            our_price=Decimal("105.00"),
            cost_price=Decimal("90.00"),
            stock_quantity=19,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    db_session.add(
        CompetitorPrice(
            product_id=24,
            competitor_name="CompOne",
            price=Decimal("100.00"),
            captured_at=datetime.now(UTC),
        )
    )
    db_session.add(
        OrderEvent(
            event_id="ord-24-current",
            product_id=24,
            quantity=2,
            customer_region="IN",
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    db_session.add(
        PriceHistory(
            product_id=24,
            old_price=Decimal("103.00"),
            new_price=Decimal("105.00"),
            change_reason="seed",
            decided_by=DecisionActor.MANUAL,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()

    rejection = await update_product_price(24, Decimal("95.00"), reason="too aggressive", session=db_session)
    assert rejection["success"] is False
    assert "minimum margin" in rejection["message"].lower()

    success = await update_product_price(24, Decimal("115.00"), reason="safe move", session=db_session)
    assert success["success"] is True
    assert success["new_price"] == Decimal("115.00")

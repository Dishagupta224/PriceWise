from __future__ import annotations

from decimal import Decimal

import pytest

from app.models import Product
from app.rule_engine import RuleDecision, RuleEngine


@pytest.mark.asyncio
async def test_small_price_changes_are_filtered(db_session):
    db_session.add(
        Product(
            id=11,
            name="Small Change Product",
            category="Books",
            description=None,
            our_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            stock_quantity=30,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    await db_session.commit()

    event = {
        "product_id": 11,
        "competitor_name": "CompOne",
        "new_price": "99.10",
        "change_percent": "1.9",
    }

    evaluation = await RuleEngine().evaluate(event, db_session)

    assert evaluation.decision is RuleDecision.IGNORE
    assert "significance threshold" in evaluation.reason


@pytest.mark.asyncio
async def test_inactive_products_are_filtered(db_session):
    db_session.add(
        Product(
            id=12,
            name="Inactive Product",
            category="Books",
            description=None,
            our_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            stock_quantity=30,
            min_margin_percent=20.0,
            is_active=False,
        )
    )
    await db_session.commit()

    event = {
        "product_id": 12,
        "competitor_name": "CompOne",
        "new_price": "92.00",
        "change_percent": "-8.0",
    }

    evaluation = await RuleEngine().evaluate(event, db_session)

    assert evaluation.decision is RuleDecision.IGNORE
    assert evaluation.reason == "Product is inactive."


@pytest.mark.asyncio
async def test_own_price_echoes_are_filtered(db_session):
    db_session.add(
        Product(
            id=13,
            name="Echo Product",
            category="Books",
            description=None,
            our_price=Decimal("140.00"),
            cost_price=Decimal("100.00"),
            stock_quantity=30,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    await db_session.commit()

    event = {
        "product_id": 13,
        "competitor_name": "CompOne",
        "source": "pricing-agent",
        "new_price": "140.00",
        "change_percent": "-6.0",
    }

    evaluation = await RuleEngine().evaluate(event, db_session)

    assert evaluation.decision is RuleDecision.IGNORE
    assert "echo" in evaluation.reason.lower()


@pytest.mark.asyncio
async def test_significant_events_pass_fast_path(db_session):
    db_session.add(
        Product(
            id=14,
            name="Pass Through Product",
            category="Books",
            description=None,
            our_price=Decimal("220.00"),
            cost_price=Decimal("120.00"),
            stock_quantity=25,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    await db_session.commit()

    event = {
        "product_id": 14,
        "competitor_name": "CompOne",
        "new_price": "210.00",
        "change_percent": "-4.55",
    }

    evaluation = await RuleEngine().evaluate(event, db_session)

    assert evaluation.decision is RuleDecision.PROCESS
    assert evaluation.reason == "Event passed fast-path checks."

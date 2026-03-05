from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.agent import PricingDecisionAgent
from app.enums import AgentDecisionType, ExecutionStatus
from app.models import CompetitorPrice, Product


def _mock_openai_response(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=None,
                    content=json.dumps(payload),
                )
            )
        ]
    )


@pytest.mark.asyncio
async def test_agent_processes_competitor_price_drop(monkeypatch, db_session):
    db_session.add(
        Product(
            id=101,
            name="Drop Candidate",
            category="Electronics",
            description=None,
            our_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            stock_quantity=40,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    db_session.add(
        CompetitorPrice(
            product_id=101,
            competitor_name="CompA",
            price=Decimal("90.00"),
            captured_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    async def fake_completion(self, _messages):
        return _mock_openai_response(
            {
                "decision_type": "PRICE_DROP",
                "reasoning": "Competitor undercut us significantly.",
                "confidence_score": 0.91,
                "proposed_price": 95.0,
                "alert_message": None,
            }
        )

    monkeypatch.setattr(PricingDecisionAgent, "_create_completion_with_retry", fake_completion)

    agent = PricingDecisionAgent()
    agent._client = object()

    result = await agent.process_event(
        {
            "event_id": "ev-101",
            "product_id": 101,
            "competitor_name": "CompA",
            "old_price": "100.00",
            "new_price": "90.00",
            "change_percent": "-10.0",
        }
    )

    assert result.decision_type is AgentDecisionType.PRICE_DROP
    assert result.execution_status is ExecutionStatus.EXECUTED
    assert result.update_result is not None
    assert result.update_result["success"] is True

    refreshed = await db_session.scalar(select(Product).where(Product.id == 101))
    assert refreshed is not None
    assert Decimal(refreshed.our_price) == Decimal("95.00")


@pytest.mark.asyncio
async def test_agent_respects_min_margin_constraints(monkeypatch, db_session):
    db_session.add(
        Product(
            id=102,
            name="Margin Sensitive",
            category="Electronics",
            description=None,
            our_price=Decimal("101.00"),
            cost_price=Decimal("95.00"),
            stock_quantity=30,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    db_session.add(
        CompetitorPrice(
            product_id=102,
            competitor_name="CompA",
            price=Decimal("95.00"),
            captured_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    async def fake_completion(self, _messages):
        return _mock_openai_response(
            {
                "decision_type": "PRICE_DROP",
                "reasoning": "Need to close the market gap.",
                "confidence_score": 0.82,
                "proposed_price": 100.0,
                "alert_message": None,
            }
        )

    monkeypatch.setattr(PricingDecisionAgent, "_create_completion_with_retry", fake_completion)

    agent = PricingDecisionAgent()
    agent._client = object()

    result = await agent.process_event(
        {
            "event_id": "ev-102",
            "product_id": 102,
            "competitor_name": "CompA",
            "old_price": "99.00",
            "new_price": "95.00",
            "change_percent": "-4.0",
        }
    )

    assert result.decision_type is AgentDecisionType.PRICE_HOLD
    assert result.execution_status is ExecutionStatus.REJECTED
    assert result.update_result is not None
    assert result.update_result["success"] is False
    assert "minimum margin" in str(result.update_result["message"]).lower()


@pytest.mark.asyncio
async def test_agent_fallback_when_openai_unreachable(monkeypatch, db_session):
    db_session.add(
        Product(
            id=103,
            name="Fallback Product",
            category="Electronics",
            description=None,
            our_price=Decimal("150.00"),
            cost_price=Decimal("90.00"),
            stock_quantity=30,
            min_margin_percent=20.0,
            is_active=True,
        )
    )
    db_session.add(
        CompetitorPrice(
            product_id=103,
            competitor_name="CompA",
            price=Decimal("130.00"),
            captured_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    async def failing_completion(self, _messages):
        raise RuntimeError("OpenAI unreachable")

    monkeypatch.setattr(PricingDecisionAgent, "_create_completion_with_retry", failing_completion)

    agent = PricingDecisionAgent()
    agent._client = object()

    result = await agent.process_event(
        {
            "event_id": "ev-103",
            "product_id": 103,
            "competitor_name": "CompA",
            "old_price": "138.00",
            "new_price": "130.00",
            "change_percent": "-5.8",
        }
    )

    assert result.decision_type is AgentDecisionType.PRICE_HOLD
    assert result.execution_status is ExecutionStatus.REJECTED
    assert "failed" in result.reasoning.lower() or "unreachable" in result.reasoning.lower()

"""Fast-path rule engine for filtering pricing events before AI reasoning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AgentDecision, Product

settings = get_settings()


class RuleDecision(StrEnum):
    """Possible outcomes of the fast-path rule engine."""

    PROCESS = "PROCESS"
    IGNORE = "IGNORE"
    DIRECT_ACTION = "DIRECT_ACTION"


@dataclass(slots=True)
class RuleEvaluation:
    """Result returned by the rule engine."""

    decision: RuleDecision
    reason: str
    direct_topic: str | None = None
    direct_payload: dict[str, object] | None = None


class RuleEngine:
    """Evaluate incoming Kafka events before sending them to the AI agent."""

    async def evaluate(self, event: dict[str, object], session: AsyncSession) -> RuleEvaluation:
        """Return PROCESS, IGNORE, or DIRECT_ACTION for one event."""
        product_id = event.get("product_id")
        if product_id is None:
            return RuleEvaluation(RuleDecision.IGNORE, "Event missing product_id.")

        product = await session.scalar(select(Product).where(Product.id == int(product_id)))
        if product is None:
            return RuleEvaluation(RuleDecision.IGNORE, f"Unknown product_id={product_id}.")
        if not product.is_active:
            return RuleEvaluation(RuleDecision.IGNORE, "Product is inactive.")

        if self._is_our_price_echo(event, product):
            return RuleEvaluation(RuleDecision.IGNORE, "Event is an echo of our own price update.")

        change_percent = Decimal(str(event.get("change_percent", "0")))
        if abs(change_percent) < Decimal(str(settings.min_significant_price_change_percent)):
            return RuleEvaluation(RuleDecision.IGNORE, "Price change is below the 2% significance threshold.")

        cooldown_result = await self._check_recent_decision_cooldown(int(product_id), session)
        if cooldown_result is not None:
            return cooldown_result

        if product.stock_quantity <= 0:
            request_id = str(event.get("request_id") or event.get("event_id") or uuid4())
            payload = {
                "event_id": str(uuid4()),
                "request_id": request_id,
                "product_id": product.id,
                "alert_type": "REORDER_ALERT",
                "current_stock": product.stock_quantity,
                "threshold": settings.low_stock_threshold,
                "reason": "Stock is 0; pricing skipped and reorder recommended.",
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
            return RuleEvaluation(
                RuleDecision.DIRECT_ACTION,
                "Stock is 0, bypassing AI pricing and triggering reorder alert.",
                direct_topic="alerts",
                direct_payload=payload,
            )

        return RuleEvaluation(RuleDecision.PROCESS, "Event passed fast-path checks.")

    async def _check_recent_decision_cooldown(
        self,
        product_id: int,
        session: AsyncSession,
    ) -> RuleEvaluation | None:
        """Skip repeated pricing reviews for a product within the configured cooldown window."""
        cutoff = datetime.now(UTC) - timedelta(minutes=settings.pricing_cooldown_minutes)
        recent_decision = await session.scalar(
            select(AgentDecision)
            .where(AgentDecision.product_id == product_id, AgentDecision.created_at >= cutoff)
            .order_by(AgentDecision.created_at.desc())
        )
        if recent_decision is None:
            return None

        return RuleEvaluation(
            RuleDecision.IGNORE,
            (
                f"Product is in pricing cooldown for {settings.pricing_cooldown_minutes} minutes. "
                f"Latest decision at {recent_decision.created_at.isoformat()}."
            ),
        )

    def _is_our_price_echo(self, event: dict[str, object], product: Product) -> bool:
        """Detect feedback-loop events caused by our own price updates."""
        source = str(event.get("source", "")).lower()
        competitor_name = str(event.get("competitor_name", "")).lower()
        new_price = event.get("new_price")

        if source in {"pricing-agent", "dashboard-api", "our-price-update"}:
            return True
        if competitor_name in {"pricewise", "our-store", "internal"}:
            return True
        if new_price is not None:
            try:
                return Decimal(str(new_price)) == Decimal(product.our_price)
            except Exception:
                return False
        return False

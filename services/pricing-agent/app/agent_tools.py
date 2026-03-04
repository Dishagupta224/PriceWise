"""Async database-backed tools exposed to the pricing agent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import DecisionActor
from app.models import CompetitorPrice, OrderEvent, PriceHistory, Product
from shared.database import AsyncSessionLocal


def to_money(value: Decimal) -> Decimal:
    """Round currency values to two decimal places."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def get_product_details(product_id: int, session: AsyncSession | None = None) -> dict[str, Any]:
    """Return core product details for the requested product."""
    async with _session_or_context(session) as db:
        product = await db.scalar(select(Product).where(Product.id == product_id))
        if product is None:
            raise ValueError(f"Product {product_id} was not found.")
        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "our_price": Decimal(product.our_price),
            "cost_price": Decimal(product.cost_price),
            "stock": product.stock_quantity,
            "min_margin_percent": product.min_margin_percent,
            "is_active": product.is_active,
        }


async def get_competitor_prices(product_id: int, session: AsyncSession | None = None) -> list[dict[str, Any]]:
    """Return the latest known price per competitor, sorted by price ascending."""
    async with _session_or_context(session) as db:
        result = await db.execute(
            select(CompetitorPrice)
            .where(CompetitorPrice.product_id == product_id)
            .order_by(CompetitorPrice.competitor_name, CompetitorPrice.captured_at.desc(), CompetitorPrice.id.desc())
        )
        rows = result.scalars().all()
        latest_by_competitor: dict[str, CompetitorPrice] = {}
        for row in rows:
            latest_by_competitor.setdefault(row.competitor_name, row)

        return [
            {
                "competitor_name": row.competitor_name,
                "price": Decimal(row.price),
                "last_updated": row.captured_at,
            }
            for row in sorted(latest_by_competitor.values(), key=lambda item: Decimal(item.price))
        ]


async def get_market_position(product_id: int, session: AsyncSession | None = None) -> dict[str, Any]:
    """Return a compact view of our current price versus the latest competitor market."""
    product = await get_product_details(product_id, session=session)
    competitor_prices = await get_competitor_prices(product_id, session=session)

    our_price = Decimal(str(product["our_price"]))
    if not competitor_prices:
        return {
            "product_id": product_id,
            "our_price": our_price,
            "cheapest_competitor_price": None,
            "average_competitor_price": None,
            "highest_competitor_price": None,
            "price_gap_to_cheapest_percent": None,
            "safe_increase_ceiling": None,
            "has_pricing_headroom": False,
        }

    prices = [Decimal(str(item["price"])) for item in competitor_prices]
    cheapest = min(prices)
    highest = max(prices)
    average = sum(prices) / Decimal(len(prices))
    gap_percent = round(float(((cheapest - our_price) / our_price) * Decimal("100")), 2)

    return {
        "product_id": product_id,
        "our_price": our_price,
        "cheapest_competitor_price": cheapest,
        "average_competitor_price": to_money(average),
        "highest_competitor_price": highest,
        "price_gap_to_cheapest_percent": gap_percent,
        "safe_increase_ceiling": cheapest,
        "has_pricing_headroom": cheapest > our_price,
    }


async def get_demand_trend(product_id: int, days: int = 7, session: AsyncSession | None = None) -> dict[str, Any]:
    """Return recent demand totals and a simple rising/falling/stable trend classification."""
    if days <= 0:
        raise ValueError("days must be greater than 0.")

    async with _session_or_context(session) as db:
        now = datetime.now(UTC)
        current_start = now - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)

        current_total = await db.scalar(
            select(func.coalesce(func.sum(OrderEvent.quantity), 0)).where(
                OrderEvent.product_id == product_id,
                OrderEvent.created_at >= current_start,
            )
        )
        previous_total = await db.scalar(
            select(func.coalesce(func.sum(OrderEvent.quantity), 0)).where(
                OrderEvent.product_id == product_id,
                OrderEvent.created_at >= previous_start,
                OrderEvent.created_at < current_start,
            )
        )

        current_total = int(current_total or 0)
        previous_total = int(previous_total or 0)
        avg_daily_orders = round(current_total / days, 2)

        if previous_total == 0:
            compared_percent = 100.0 if current_total > 0 else 0.0
        else:
            compared_percent = round(((current_total - previous_total) / previous_total) * 100, 2)

        if compared_percent > 10:
            trend = "rising"
        elif compared_percent < -10:
            trend = "falling"
        else:
            trend = "stable"

        return {
            "total_orders": current_total,
            "avg_daily_orders": avg_daily_orders,
            "trend": trend,
            "compared_to_previous_period_percent": compared_percent,
        }


async def calculate_margin(
    product_id: int,
    proposed_price: Decimal,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Return the margin impact of a proposed price and whether it passes the minimum threshold."""
    if proposed_price <= 0:
        raise ValueError("proposed_price must be greater than 0.")

    async with _session_or_context(session) as db:
        product = await db.scalar(select(Product).where(Product.id == product_id))
        if product is None:
            raise ValueError(f"Product {product_id} was not found.")

        cost_price = Decimal(product.cost_price)
        proposed_price = Decimal(proposed_price)
        profit_per_unit = to_money(proposed_price - cost_price)
        margin_percent = round(float(((proposed_price - cost_price) / proposed_price) * Decimal("100")), 2)

        return {
            "margin_percent": margin_percent,
            "profit_per_unit": profit_per_unit,
            "passes_min_margin": margin_percent >= product.min_margin_percent,
            "min_margin_threshold": product.min_margin_percent,
        }


async def get_price_history(product_id: int, days: int = 30, session: AsyncSession | None = None) -> list[dict[str, Any]]:
    """Return recent price change history for the requested product."""
    if days <= 0:
        raise ValueError("days must be greater than 0.")

    async with _session_or_context(session) as db:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.product_id == product_id, PriceHistory.created_at >= cutoff)
            .order_by(PriceHistory.created_at.desc())
        )
        rows = result.scalars().all()
        return [
            {
                "old_price": Decimal(row.old_price),
                "new_price": Decimal(row.new_price),
                "reason": row.change_reason,
                "timestamp": row.created_at,
            }
            for row in rows
        ]


async def update_product_price(
    product_id: int,
    new_price: Decimal,
    reason: str,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Update a product's price, append price history, and return the execution status."""
    if new_price <= 0:
        raise ValueError("new_price must be greater than 0.")
    if not reason.strip():
        raise ValueError("reason must not be empty.")

    async with _session_or_context(session) as db:
        product = await db.scalar(select(Product).where(Product.id == product_id))
        if product is None:
            raise ValueError(f"Product {product_id} was not found.")

        old_price = Decimal(product.our_price)
        margin_data = await calculate_margin(product_id, Decimal(new_price), session=db)
        if not margin_data["passes_min_margin"]:
            return {
                "success": False,
                "product_id": product_id,
                "message": "Proposed price violates minimum margin threshold.",
                "old_price": old_price,
                "new_price": Decimal(new_price),
            }

        product.our_price = to_money(Decimal(new_price))
        db.add(
            PriceHistory(
                product_id=product_id,
                old_price=old_price,
                new_price=product.our_price,
                change_reason=reason,
                decided_by=DecisionActor.AGENT,
                created_at=datetime.now(UTC),
            )
        )
        await db.commit()

        return {
            "success": True,
            "product_id": product_id,
            "message": "Product price updated successfully.",
            "old_price": old_price,
            "new_price": Decimal(product.our_price),
        }


def _session_or_context(session: AsyncSession | None):
    """Return an async context manager for either a provided or new session."""
    if session is not None:
        return _ExistingSessionContext(session)
    return AsyncSessionLocal()


@dataclass
class _ExistingSessionContext:
    """No-op async context manager for an already-open session."""

    session: AsyncSession

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, *_: object) -> None:
        return None


OPENAI_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Fetch the full product context required for a pricing decision.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_competitor_prices",
            "description": "Fetch the latest known competitor prices for a product, sorted cheapest first.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_demand_trend",
            "description": "Summarize recent order demand and compare it to the previous period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "days": {"type": "integer", "default": 7},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_position",
            "description": "Compare our current price to the latest competitor market and identify safe upward-pricing headroom.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_margin",
            "description": "Check whether a proposed price preserves margin requirements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "proposed_price": {"type": "number"},
                },
                "required": ["product_id", "proposed_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": "Return recent price change history with timestamps and reasons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "days": {"type": "integer", "default": 30},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_product_price",
            "description": "Execute a product price change and record it in price_history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "new_price": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["product_id", "new_price", "reason"],
            },
        },
    },
]

OPENAI_TOOL_FUNCTIONS = {
    "get_product_details": get_product_details,
    "get_competitor_prices": get_competitor_prices,
    "get_market_position": get_market_position,
    "get_demand_trend": get_demand_trend,
    "calculate_margin": calculate_margin,
    "get_price_history": get_price_history,
    "update_product_price": update_product_price,
}

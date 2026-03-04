"""Decision and analytics read routes for the dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import AgentDecision, CompetitorPrice, PriceHistory, Product
from app.schemas import (
    AnalyticsSummaryResponse,
    DecisionDetailResponse,
    DecisionListItem,
    PaginatedDecisionsResponse,
    PaginationMeta,
    TopMoverItem,
    TopMoversResponse,
)

router = APIRouter(tags=["dashboard"])


def _pagination(page: int, page_size: int, total_items: int) -> PaginationMeta:
    """Build standard pagination metadata."""
    total_pages = max(1, ceil(total_items / page_size)) if total_items else 1
    return PaginationMeta(page=page, page_size=page_size, total_items=total_items, total_pages=total_pages)


@router.get("/decisions", response_model=PaginatedDecisionsResponse)
async def list_decisions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    decision_type: str | None = Query(default=None),
    product_id: int | None = Query(default=None, ge=1),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedDecisionsResponse:
    """Return paginated decision summaries with filters."""
    filters = []
    if decision_type:
        filters.append(AgentDecision.decision_type == decision_type)
    if product_id is not None:
        filters.append(AgentDecision.product_id == product_id)
    if date_from is not None:
        filters.append(AgentDecision.created_at >= date_from)
    if date_to is not None:
        filters.append(AgentDecision.created_at <= date_to)

    count_stmt = select(func.count()).select_from(AgentDecision)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total_items = int((await session.execute(count_stmt)).scalar_one())

    stmt = (
        select(AgentDecision, Product.name)
        .join(Product, Product.id == AgentDecision.product_id)
        .order_by(AgentDecision.created_at.desc(), AgentDecision.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(*filters)

    rows = (await session.execute(stmt)).all()
    items = [
        DecisionListItem(
            id=decision.id,
            product_id=decision.product_id,
            product_name=product_name,
            decision_type=decision.decision_type,
            execution_status=decision.execution_status,
            confidence_score=decision.confidence_score,
            reasoning_preview=(decision.reasoning[:100] + "...") if len(decision.reasoning) > 100 else decision.reasoning,
            created_at=decision.created_at,
        )
        for decision, product_name in rows
    ]
    return PaginatedDecisionsResponse(items=items, pagination=_pagination(page, page_size, total_items))


@router.get("/decisions/{decision_id}", response_model=DecisionDetailResponse)
async def get_decision(decision_id: int, session: AsyncSession = Depends(get_db_session)) -> DecisionDetailResponse:
    """Return a single decision with full reasoning and related price change context."""
    row = (
        await session.execute(
            select(AgentDecision, Product.name, Product.our_price)
            .join(Product, Product.id == AgentDecision.product_id)
            .where(AgentDecision.id == decision_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found.")

    decision, product_name, current_price = row
    price_history = (
        await session.execute(
            select(PriceHistory)
            .where(
                PriceHistory.product_id == decision.product_id,
                PriceHistory.decided_by == "AGENT",
                PriceHistory.created_at <= decision.created_at + timedelta(minutes=5),
                PriceHistory.created_at >= decision.created_at - timedelta(minutes=5),
            )
            .order_by(func.abs(func.extract("epoch", PriceHistory.created_at - decision.created_at)))
            .limit(1)
        )
    ).scalar_one_or_none()

    return DecisionDetailResponse(
        id=decision.id,
        product_id=decision.product_id,
        product_name=product_name,
        decision_type=decision.decision_type,
        execution_status=decision.execution_status,
        confidence_score=decision.confidence_score,
        reasoning=decision.reasoning,
        tools_used=decision.tools_used,
        before_price=Decimal(price_history.old_price) if price_history else Decimal(current_price),
        after_price=Decimal(price_history.new_price) if price_history else Decimal(current_price),
        created_at=decision.created_at,
    )


@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(session: AsyncSession = Depends(get_db_session)) -> AnalyticsSummaryResponse:
    """Return top-line dashboard summary metrics."""
    now = datetime.now(UTC)
    today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)

    total_active_products = int(
        (await session.execute(select(func.count()).select_from(Product).where(Product.is_active.is_(True)))).scalar_one()
    )
    total_decisions_today = int(
        (await session.execute(select(func.count()).select_from(AgentDecision).where(AgentDecision.created_at >= today_start))).scalar_one()
    )

    margin_expr = ((Product.our_price - Product.cost_price) / Product.our_price) * Decimal("100")
    avg_margin = (
        await session.execute(select(func.avg(margin_expr)).where(Product.is_active.is_(True), Product.our_price > 0))
    ).scalar_one()
    avg_margin_percent = round(float(avg_margin or 0), 2)

    revenue_impact = (
        await session.execute(
            select(func.coalesce(func.sum(PriceHistory.new_price - PriceHistory.old_price), 0))
            .where(PriceHistory.decided_by == "AGENT", PriceHistory.created_at >= today_start)
        )
    ).scalar_one()

    latest_competitor = (
        select(
            CompetitorPrice.product_id.label("product_id"),
            func.max(CompetitorPrice.captured_at).label("captured_at"),
        )
        .group_by(CompetitorPrice.product_id)
        .subquery()
    )
    overpriced_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Product)
                .join(latest_competitor, latest_competitor.c.product_id == Product.id)
                .join(
                    CompetitorPrice,
                    and_(
                        CompetitorPrice.product_id == latest_competitor.c.product_id,
                        CompetitorPrice.captured_at == latest_competitor.c.captured_at,
                    ),
                )
                .where(Product.is_active.is_(True), Product.our_price > CompetitorPrice.price)
            )
        ).scalar_one()
    )

    low_stock_products = int(
        (await session.execute(select(func.count()).select_from(Product).where(Product.is_active.is_(True), Product.stock_quantity <= 15))).scalar_one()
    )
    products_needing_attention = low_stock_products + overpriced_count

    return AnalyticsSummaryResponse(
        total_active_products=total_active_products,
        total_decisions_today=total_decisions_today,
        avg_margin_percent=avg_margin_percent,
        total_revenue_impact=Decimal(revenue_impact).quantize(Decimal("0.01")),
        products_needing_attention=products_needing_attention,
        low_stock_products=low_stock_products,
        overpriced_products=overpriced_count,
    )


@router.get("/analytics/top-movers", response_model=TopMoversResponse)
async def get_top_movers(session: AsyncSession = Depends(get_db_session)) -> TopMoversResponse:
    """Return the top 10 products with the biggest price changes in the last 24 hours."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    rows = (
        await session.execute(
            select(PriceHistory, Product.name)
            .join(Product, Product.id == PriceHistory.product_id)
            .where(PriceHistory.created_at >= cutoff)
            .order_by(func.abs((PriceHistory.new_price - PriceHistory.old_price) / PriceHistory.old_price).desc())
            .limit(10)
        )
    ).all()

    items = []
    for price_change, product_name in rows:
        old_price = Decimal(price_change.old_price)
        new_price = Decimal(price_change.new_price)
        percent = 0.0 if old_price <= 0 else round(float(((new_price - old_price) / old_price) * Decimal("100")), 2)
        items.append(
            TopMoverItem(
                product_id=price_change.product_id,
                product_name=product_name,
                old_price=old_price,
                new_price=new_price,
                percentage_change=percent,
                direction="up" if new_price > old_price else "down",
                reason=price_change.change_reason,
                created_at=price_change.created_at,
            )
        )
    return TopMoversResponse(items=items)

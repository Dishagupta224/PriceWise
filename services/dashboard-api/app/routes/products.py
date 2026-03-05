"""Product read/write routes with dashboard-focused enrichment."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db_session
from app.models import CompetitorPrice, PriceHistory, Product
from app.schemas import (
    CompetitorPriceRead,
    CompetitorSnapshot,
    PaginatedProductsResponse,
    PaginationMeta,
    PriceHistoryPoint,
    ProductCreate,
    ProductDetailResponse,
    ProductListItem,
    ProductPriceHistoryResponse,
    ProductRead,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])

SORT_COLUMNS = {
    "price": Product.our_price,
    "stock": Product.stock_quantity,
    "name": Product.name,
    "last_updated": Product.updated_at,
}


async def _get_product_or_404(session: AsyncSession, product_id: int) -> Product:
    """Fetch a product with related data or raise a 404."""
    result = await session.execute(
        select(Product)
        .options(
            selectinload(Product.competitor_prices),
            selectinload(Product.price_history),
            selectinload(Product.agent_decisions),
        )
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product


def _validate_margin(product: Product) -> None:
    """Apply pricing constraints to create and update operations."""
    margin_multiplier = Decimal("1") + (Decimal(str(product.min_margin_percent)) / Decimal("100"))
    minimum_price = Decimal(product.cost_price) * margin_multiplier
    if Decimal(product.our_price) < minimum_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="our_price must satisfy the configured minimum margin percent.",
        )


def _build_pagination(page: int, page_size: int, total_items: int) -> PaginationMeta:
    """Return response pagination metadata."""
    total_pages = max(1, ceil(total_items / page_size)) if total_items else 1
    return PaginationMeta(page=page, page_size=page_size, total_items=total_items, total_pages=total_pages)


def _margin_percent(our_price: Decimal, cost_price: Decimal) -> float:
    """Compute current gross margin percentage."""
    if our_price <= 0:
        return 0.0
    return round(float(((our_price - cost_price) / our_price) * Decimal("100")), 2)


async def _latest_competitors_by_product(
    session: AsyncSession,
    product_ids: list[int],
) -> dict[int, list[CompetitorSnapshot]]:
    """Return latest competitor prices for each requested product."""
    if not product_ids:
        return {}

    latest_ts = (
        select(
            CompetitorPrice.product_id.label("product_id"),
            CompetitorPrice.competitor_name.label("competitor_name"),
            func.max(CompetitorPrice.captured_at).label("captured_at"),
        )
        .where(CompetitorPrice.product_id.in_(product_ids))
        .group_by(CompetitorPrice.product_id, CompetitorPrice.competitor_name)
        .subquery()
    )

    result = await session.execute(
        select(CompetitorPrice)
        .join(
            latest_ts,
            and_(
                CompetitorPrice.product_id == latest_ts.c.product_id,
                CompetitorPrice.competitor_name == latest_ts.c.competitor_name,
                CompetitorPrice.captured_at == latest_ts.c.captured_at,
            ),
        )
        .order_by(CompetitorPrice.product_id, CompetitorPrice.price.asc(), CompetitorPrice.competitor_name.asc())
    )

    grouped: dict[int, list[CompetitorSnapshot]] = defaultdict(list)
    for row in result.scalars():
        grouped[row.product_id].append(
            CompetitorSnapshot(
                competitor_name=row.competitor_name,
                price=Decimal(row.price),
                captured_at=row.captured_at,
            )
        )
    return grouped


async def _price_change_24h_by_product(session: AsyncSession, product_ids: list[int]) -> dict[int, float]:
    """Return percentage price change in the last 24 hours for each product."""
    if not product_ids:
        return {}

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    result = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.product_id.in_(product_ids), PriceHistory.created_at >= cutoff)
        .order_by(PriceHistory.product_id.asc(), PriceHistory.created_at.desc())
    )

    changes: dict[int, float] = {}
    for row in result.scalars():
        if row.product_id in changes:
            continue
        if Decimal(row.old_price) <= 0:
            changes[row.product_id] = 0.0
            continue
        changes[row.product_id] = round(
            float(((Decimal(row.new_price) - Decimal(row.old_price)) / Decimal(row.old_price)) * Decimal("100")),
            2,
        )
    return changes


def _to_product_item(
    product: Product,
    latest_competitors: list[CompetitorSnapshot],
    price_change_24h: float,
) -> ProductListItem:
    """Serialize a product into the enriched list/detail shape."""
    return ProductListItem(
        id=product.id,
        name=product.name,
        category=product.category,
        description=product.description,
        our_price=Decimal(product.our_price),
        cost_price=Decimal(product.cost_price),
        stock_quantity=product.stock_quantity,
        min_margin_percent=product.min_margin_percent,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
        current_margin_percent=_margin_percent(Decimal(product.our_price), Decimal(product.cost_price)),
        price_change_24h=price_change_24h,
        latest_competitor_prices=latest_competitors,
    )


@router.get("", response_model=PaginatedProductsResponse)
async def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="name", pattern="^(price|stock|name|last_updated)$"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    category: str | None = Query(default=None),
    stock_status: str | None = Query(default=None, pattern="^(low|normal|out)$"),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedProductsResponse:
    """Return paginated products with filters, sorting, and computed pricing context."""
    filters = []
    if category:
        filters.append(Product.category == category)
    if stock_status == "low":
        filters.append(and_(Product.stock_quantity > 0, Product.stock_quantity <= 15))
    elif stock_status == "normal":
        filters.append(Product.stock_quantity > 15)
    elif stock_status == "out":
        filters.append(Product.stock_quantity <= 0)

    count_stmt = select(func.count()).select_from(Product)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total_items = int((await session.execute(count_stmt)).scalar_one())

    order_column = SORT_COLUMNS[sort_by]
    if sort_order == "desc":
        order_column = order_column.desc()
    else:
        order_column = order_column.asc()

    stmt: Select[tuple[Product]] = select(Product).order_by(order_column, Product.id.asc())
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    products = list((await session.execute(stmt)).scalars().all())
    product_ids = [product.id for product in products]
    latest_competitors = await _latest_competitors_by_product(session, product_ids)
    price_change_24h = await _price_change_24h_by_product(session, product_ids)

    items = [
        _to_product_item(product, latest_competitors.get(product.id, []), price_change_24h.get(product.id, 0.0))
        for product in products
    ]
    return PaginatedProductsResponse(items=items, pagination=_build_pagination(page, page_size, total_items))


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(product_id: int, session: AsyncSession = Depends(get_db_session)) -> ProductDetailResponse:
    """Return one product with enriched current pricing context."""
    product = await _get_product_or_404(session, product_id)
    latest_competitors = await _latest_competitors_by_product(session, [product_id])
    price_change_24h = await _price_change_24h_by_product(session, [product_id])
    item = _to_product_item(product, latest_competitors.get(product.id, []), price_change_24h.get(product.id, 0.0))
    return ProductDetailResponse(**item.model_dump(), competitor_prices=[CompetitorPriceRead.model_validate(row) for row in product.competitor_prices])


@router.get("/{product_id}/price-history", response_model=ProductPriceHistoryResponse)
async def get_product_price_history(
    product_id: int,
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_db_session),
) -> ProductPriceHistoryResponse:
    """Return chart-ready product price history with our price and competitor prices."""
    product = await _get_product_or_404(session, product_id)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    our_price_result = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id, PriceHistory.created_at >= cutoff)
        .order_by(PriceHistory.created_at.asc())
    )
    competitor_result = await session.execute(
        select(CompetitorPrice)
        .where(CompetitorPrice.product_id == product_id, CompetitorPrice.captured_at >= cutoff)
        .order_by(CompetitorPrice.captured_at.asc())
    )

    points: list[PriceHistoryPoint] = [
        PriceHistoryPoint(timestamp=row.created_at, our_price=Decimal(row.new_price))
        for row in our_price_result.scalars()
    ]
    points.extend(
        PriceHistoryPoint(
            timestamp=row.captured_at,
            competitor_name=row.competitor_name,
            competitor_price=Decimal(row.price),
        )
        for row in competitor_result.scalars()
    )
    if not points:
        points.append(PriceHistoryPoint(timestamp=product.updated_at, our_price=Decimal(product.our_price)))

    points.sort(key=lambda point: point.timestamp)
    return ProductPriceHistoryResponse(product_id=product.id, product_name=product.name, days=days, points=points)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_db_session),
) -> Product:
    """Create a new product record."""
    product = Product(**payload.model_dump())
    _validate_margin(product)
    session.add(product)
    await session.commit()
    return await _get_product_or_404(session, product.id)


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> Product:
    """Update an existing product."""
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update.")

    for field, value in update_data.items():
        setattr(product, field, value)

    _validate_margin(product)
    await session.commit()
    return await _get_product_or_404(session, product_id)


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete an existing product."""
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    await session.delete(product)
    await session.commit()
    return {"status": "deleted"}

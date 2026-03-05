from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[3]
SERVICES_DIR = ROOT / "services"
DASHBOARD_DIR = SERVICES_DIR / "dashboard-api"

for path in (str(DASHBOARD_DIR), str(SERVICES_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./dashboard-api-tests-bootstrap.db")

from app.database import get_db_session
from app.enums import AgentDecisionType, DecisionActor, ExecutionStatus
from app.models import AgentDecision, Base, CompetitorPrice, PriceHistory, Product
from app.routes.dashboard import router as dashboard_router
from app.routes.products import router as products_router


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path):
    db_file = tmp_path / "dashboard_api_tests.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield session_maker
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def test_app(session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(products_router, prefix="/api")
    app.include_router(products_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api/v1")

    async def _override_get_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    return app


@pytest_asyncio.fixture
async def client(test_app: FastAPI):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def seed_dashboard_data(session_factory):
    async with session_factory() as session:
        products: list[Product] = []
        now = datetime.now(UTC)
        for idx in range(1, 26):
            stock = 8 if idx % 5 == 0 else 40 + idx
            category = "Electronics" if idx % 2 == 0 else "Books"
            product = Product(
                id=idx,
                name=f"Product {idx}",
                category=category,
                description=f"Description {idx}",
                our_price=Decimal("100.00") + Decimal(str(idx)),
                cost_price=Decimal("60.00"),
                stock_quantity=stock,
                min_margin_percent=20.0,
                is_active=True,
            )
            products.append(product)
            session.add(product)
            session.add(
                CompetitorPrice(
                    product_id=idx,
                    competitor_name="CompA",
                    price=Decimal("98.00") + Decimal(str(idx)),
                    captured_at=now - timedelta(minutes=idx),
                )
            )

        session.add_all(
            [
                AgentDecision(
                    product_id=1,
                    decision_type=AgentDecisionType.PRICE_DROP,
                    reasoning="Drop for competitiveness.",
                    confidence_score=0.9,
                    tools_used=["get_market_position"],
                    execution_status=ExecutionStatus.EXECUTED,
                    created_at=now - timedelta(hours=1),
                ),
                AgentDecision(
                    product_id=2,
                    decision_type=AgentDecisionType.PRICE_HOLD,
                    reasoning="Hold due to stable demand.",
                    confidence_score=0.7,
                    tools_used=["get_demand_trend"],
                    execution_status=ExecutionStatus.EXECUTED,
                    created_at=now - timedelta(hours=2),
                ),
                AgentDecision(
                    product_id=1,
                    decision_type=AgentDecisionType.PRICE_INCREASE,
                    reasoning="Increase with headroom.",
                    confidence_score=0.8,
                    tools_used=["get_market_position", "calculate_margin"],
                    execution_status=ExecutionStatus.EXECUTED,
                    created_at=now - timedelta(days=2),
                ),
            ]
        )

        for idx in range(4, 26):
            session.add(
                AgentDecision(
                    product_id=(idx % 3) + 1,
                    decision_type=AgentDecisionType.PRICE_HOLD if idx % 2 else AgentDecisionType.PRICE_DROP,
                    reasoning=f"Decision {idx}",
                    confidence_score=0.55,
                    tools_used=[],
                    execution_status=ExecutionStatus.EXECUTED,
                    created_at=now - timedelta(minutes=idx),
                )
            )

        session.add_all(
            [
                PriceHistory(
                    product_id=1,
                    old_price=Decimal("104.00"),
                    new_price=Decimal("100.00"),
                    change_reason="Agent change",
                    decided_by=DecisionActor.AGENT,
                    created_at=now - timedelta(hours=1),
                ),
                PriceHistory(
                    product_id=2,
                    old_price=Decimal("101.00"),
                    new_price=Decimal("103.00"),
                    change_reason="Agent increase",
                    decided_by=DecisionActor.AGENT,
                    created_at=now - timedelta(hours=2),
                ),
            ]
        )

        await session.commit()

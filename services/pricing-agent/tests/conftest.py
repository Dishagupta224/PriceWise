from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[3]
SERVICES_DIR = ROOT / "services"
PRICING_AGENT_DIR = SERVICES_DIR / "pricing-agent"

for path in (str(PRICING_AGENT_DIR), str(SERVICES_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./pricing-agent-tests-bootstrap.db")

from app.enums import AgentDecisionType, DecisionActor, ExecutionStatus
from app.models import AgentDecision, Base, CompetitorPrice, OrderEvent, PriceHistory, Product
import app.agent as agent_module
import app.agent_tools as agent_tools_module
import shared.database as shared_database


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "pricing_agent_tests.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(shared_database, "AsyncSessionLocal", session_maker)
    monkeypatch.setattr(agent_tools_module, "AsyncSessionLocal", session_maker)
    monkeypatch.setattr(agent_module, "AsyncSessionLocal", session_maker)
    monkeypatch.setattr(shared_database, "engine", engine)

    try:
        yield session_maker
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_product(db_session: AsyncSession):
    product = Product(
        id=1,
        name="Seeded Product",
        category="Electronics",
        description="Fixture product",
        our_price=Decimal("100.00"),
        cost_price=Decimal("60.00"),
        stock_quantity=50,
        min_margin_percent=20.0,
        is_active=True,
    )
    db_session.add(product)
    db_session.add_all(
        [
            CompetitorPrice(
                product_id=1,
                competitor_name="CompA",
                price=Decimal("92.00"),
                captured_at=datetime.now(UTC) - timedelta(hours=1),
            ),
            CompetitorPrice(
                product_id=1,
                competitor_name="CompB",
                price=Decimal("96.00"),
                captured_at=datetime.now(UTC) - timedelta(hours=1),
            ),
            OrderEvent(
                event_id="order-current-1",
                product_id=1,
                quantity=8,
                customer_region="IN",
                created_at=datetime.now(UTC) - timedelta(days=2),
            ),
            OrderEvent(
                event_id="order-previous-1",
                product_id=1,
                quantity=3,
                customer_region="IN",
                created_at=datetime.now(UTC) - timedelta(days=10),
            ),
            PriceHistory(
                product_id=1,
                old_price=Decimal("98.00"),
                new_price=Decimal("100.00"),
                change_reason="Initial fixture history",
                decided_by=DecisionActor.MANUAL,
                created_at=datetime.now(UTC) - timedelta(days=1),
            ),
            AgentDecision(
                product_id=1,
                decision_type=AgentDecisionType.PRICE_HOLD,
                reasoning="Fixture prior decision",
                confidence_score=0.55,
                tools_used=[],
                execution_status=ExecutionStatus.EXECUTED,
                created_at=datetime.now(UTC) - timedelta(days=2),
            ),
        ]
    )
    await db_session.commit()
    return product

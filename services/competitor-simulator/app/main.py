"""Continuous competitor price simulator service."""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import CompetitorPrice, Product
from shared.kafka_utils import AsyncKafkaProducer
from shared.observability import clear_request_id, configure_logging, ensure_request_id, touch_healthcheck

settings = get_settings()

configure_logging("competitor-simulator", settings.log_level)
logger = logging.getLogger(__name__)

COMPETITORS = ("FlipMart", "QuickBazaar", "DealDirect")


@dataclass(frozen=True)
class ScenarioPlan:
    """Controls how often a market pattern appears and how far competitors sit from our price."""

    label: str
    relative_to_our_price_min: Decimal
    relative_to_our_price_max: Decimal
    weight: float


NEUTRAL_SCENARIO = ScenarioPlan("neutral-market", Decimal("0.99"), Decimal("1.02"), 0.50)
DROP_SCENARIO = ScenarioPlan("drop-pressure", Decimal("0.97"), Decimal("0.99"), 0.30)
INCREASE_SCENARIO = ScenarioPlan("increase-headroom", Decimal("1.02"), Decimal("1.05"), 0.20)
SCENARIOS = (NEUTRAL_SCENARIO, DROP_SCENARIO, INCREASE_SCENARIO)


def to_money(value: Decimal) -> Decimal:
    """Round to two decimal places for currency storage."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CompetitorPriceSimulator:
    """Generates competitor events with a balanced mix of hold, drop, and increase pressure."""

    def __init__(self) -> None:
        self._producer = AsyncKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        self._random = random.Random()
        self._health_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        """Start Kafka and enter the infinite simulation loop."""
        await self._producer.start()
        self._health_task = asyncio.create_task(self._healthbeat_loop(), name="competitor-simulator-health")
        logger.info(
            "Competitor simulator started. interval=%ss-%ss speed=%sx demo_profile=%s mix=50%% neutral 30%% drop 20%% increase",
            settings.effective_min_interval_seconds,
            settings.effective_max_interval_seconds,
            settings.effective_simulation_speed,
            settings.is_demo_profile,
        )
        try:
            while True:
                await self._simulate_one_change()
                base_interval = self._random.randint(
                    settings.effective_min_interval_seconds,
                    settings.effective_max_interval_seconds,
                )
                effective_interval = max(base_interval / max(settings.effective_simulation_speed, 0.1), 1)
                await asyncio.sleep(effective_interval)
        finally:
            if self._health_task is not None:
                self._health_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._health_task
            await self._producer.stop()

    async def _simulate_one_change(self) -> None:
        """Pick one product and competitor, simulate a price change, and publish it."""
        try:
            async with AsyncSessionLocal() as session:
                scenario = self._pick_scenario()
                product = await self._pick_product_for_scenario(session, scenario)
                if product is None:
                    logger.warning("No active products found. Simulator iteration skipped.")
                    return

                competitor_name = self._random.choice(COMPETITORS)
                previous_price = await self._get_previous_price(session, product.id, competitor_name) or Decimal(product.our_price)
                old_price = to_money(previous_price)
                new_price = self._calculate_new_price(
                    product=product,
                    competitor_name=competitor_name,
                    old_price=old_price,
                    scenario=scenario,
                )
                change_percent = ((new_price - old_price) / old_price * Decimal("100")).quantize(
                    Decimal("0.1"),
                    rounding=ROUND_HALF_UP,
                )
                timestamp = datetime.now(UTC)

                row = CompetitorPrice(
                    product_id=product.id,
                    competitor_name=competitor_name,
                    price=new_price,
                    captured_at=timestamp,
                )
                session.add(row)
                await session.commit()

                event = {
                    "event_id": str(uuid4()),
                    "product_id": product.id,
                    "competitor_name": competitor_name,
                    "old_price": old_price,
                    "new_price": new_price,
                    "change_percent": change_percent,
                    "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                }
                request_id = ensure_request_id(event)
                await self._producer.send("price-changes", event, key=f"{product.id}:{competitor_name}")

                logger.info(
                    "Published competitor price change: request_id=%s product_id=%s product=%s competitor=%s old=%s new=%s change=%s%% scenario=%s stock=%s",
                    request_id,
                    product.id,
                    product.name,
                    competitor_name,
                    old_price,
                    new_price,
                    change_percent,
                    scenario.label,
                    product.stock_quantity,
                )
        finally:
            clear_request_id()

    def _pick_scenario(self) -> ScenarioPlan:
        """Return a market scenario using the target 60/25/15 mix."""
        return self._random.choices(SCENARIOS, weights=[scenario.weight for scenario in SCENARIOS], k=1)[0]

    async def _pick_product_for_scenario(self, session: AsyncSession, scenario: ScenarioPlan) -> Product | None:
        """Choose products that make the selected scenario credible."""
        result = await session.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.id))
        products = result.scalars().all()
        if not products:
            return None

        if scenario is INCREASE_SCENARIO:
            low_stock = [product for product in products if product.stock_quantity <= 15]
            if low_stock:
                return self._random.choice(low_stock)
            return min(products, key=lambda product: product.stock_quantity)

        if scenario is DROP_SCENARIO:
            healthy_stock = [product for product in products if product.stock_quantity >= 25]
            if healthy_stock:
                return self._random.choice(healthy_stock)

        return self._random.choice(products)

    async def _get_previous_price(self, session: AsyncSession, product_id: int, competitor_name: str) -> Decimal | None:
        """Fetch the latest competitor price for one product and competitor."""
        stmt: Select[tuple[CompetitorPrice]] = (
            select(CompetitorPrice)
            .where(
                CompetitorPrice.product_id == product_id,
                CompetitorPrice.competitor_name == competitor_name,
            )
            .order_by(CompetitorPrice.captured_at.desc(), CompetitorPrice.id.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        latest = result.scalar_one_or_none()
        return Decimal(latest.price) if latest is not None else None

    def _calculate_new_price(
        self,
        *,
        product: Product,
        competitor_name: str,
        old_price: Decimal,
        scenario: ScenarioPlan,
    ) -> Decimal:
        """Place the competitor above or below our price based on the chosen scenario."""
        multiplier = Decimal(
            str(self._random.uniform(float(scenario.relative_to_our_price_min), float(scenario.relative_to_our_price_max)))
        )
        target_price = Decimal(product.our_price) * multiplier

        if competitor_name == "QuickBazaar":
            target_price *= Decimal(str(self._random.uniform(0.99, 1.02)))
        elif competitor_name == "DealDirect" and scenario is DROP_SCENARIO:
            target_price *= Decimal("0.98")
        elif competitor_name == "FlipMart" and scenario is INCREASE_SCENARIO and product.category == "Electronics":
            target_price *= Decimal("1.01")

        floor_price = Decimal(product.our_price) * Decimal("0.97")
        floor_price = max(floor_price, Decimal(product.cost_price) * Decimal("1.02"))
        ceiling_price = Decimal(product.our_price) * Decimal("1.05")
        bounded_price = min(max(target_price, floor_price), ceiling_price)

        if bounded_price == old_price:
            nudge = Decimal("-0.02") if scenario is DROP_SCENARIO else Decimal("0.02")
            bounded_price = min(max(old_price + nudge, floor_price), ceiling_price)

        return to_money(bounded_price)

    async def _healthbeat_loop(self) -> None:
        """Refresh healthcheck heartbeat while service runs."""
        while True:
            touch_healthcheck(settings.healthcheck_file)
            await asyncio.sleep(10)


async def main() -> None:
    """Entrypoint for the long-running simulator."""
    simulator = CompetitorPriceSimulator()
    await simulator.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Competitor simulator stopped.")

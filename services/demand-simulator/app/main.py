"""Continuous demand and order simulator service."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Product
from shared.kafka_utils import AsyncKafkaProducer

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [demand-simulator] %(message)s",
)
logger = logging.getLogger(__name__)

REGIONS = ("Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Pune", "Chennai", "Kolkata")
BASELINE_WEIGHT = 0.50
STEADY_WEIGHT = 0.30
SCARCITY_WEIGHT = 0.20


class DemandSimulator:
    """Generates weighted customer order events."""

    def __init__(self) -> None:
        self._producer = AsyncKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        self._random = random.Random()

    async def run(self) -> None:
        """Start Kafka and continuously publish order events."""
        await self._producer.start()
        logger.info(
            "Demand simulator started. Interval range: %ss-%ss. simulation_speed=%sx",
            settings.simulation_min_interval_seconds,
            settings.simulation_max_interval_seconds,
            settings.simulation_speed,
        )
        try:
            while True:
                await self._simulate_order()
                base_interval = self._random.randint(
                    settings.simulation_min_interval_seconds,
                    settings.simulation_max_interval_seconds,
                )
                effective_interval = max(base_interval / max(settings.simulation_speed, 0.1), 1)
                await asyncio.sleep(effective_interval)
        finally:
            await self._producer.stop()

    async def _simulate_order(self) -> None:
        """Generate and publish one order event."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Product).where(Product.is_active.is_(True), Product.stock_quantity > 0).order_by(Product.id)
            )
            products = result.scalars().all()
            if not products:
                logger.warning("No in-stock active products available. Demand iteration skipped.")
                return

            scenario = self._pick_scenario()
            product = self._pick_product(products, scenario)
            quantity = self._pick_quantity(product, scenario)
            quantity = min(quantity, product.stock_quantity)
            timestamp = datetime.now(UTC)

            event = {
                "event_id": str(uuid4()),
                "product_id": product.id,
                "quantity": quantity,
                "customer_region": self._random.choice(REGIONS),
                "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            }
            await self._producer.send("orders", event, key=str(product.id))

            logger.info(
                "Published order event: product_id=%s product=%s category=%s quantity=%s region=%s price=%s scenario=%s",
                product.id,
                product.name,
                product.category,
                quantity,
                event["customer_region"],
                product.our_price,
                scenario,
            )

    def _pick_scenario(self) -> str:
        """Choose between baseline traffic, steady buying, and scarcity bursts."""
        return self._random.choices(
            ("baseline", "steady", "scarcity"),
            weights=(BASELINE_WEIGHT, STEADY_WEIGHT, SCARCITY_WEIGHT),
            k=1,
        )[0]

    def _pick_product(self, products: list[Product], scenario: str) -> Product:
        """Favor low-priced items normally and low-stock items during scarcity bursts."""
        if scenario == "scarcity":
            low_stock = [product for product in products if product.stock_quantity <= 15]
            if low_stock:
                return self._random.choice(low_stock)
            return min(products, key=lambda product: product.stock_quantity)

        weights: list[float] = []
        for product in products:
            base_weight = float(Decimal("25000") / (Decimal(product.our_price) + Decimal("250")))
            if product.category == "Electronics":
                base_weight *= 1.35 if self._random.random() < 0.25 else 1.05
            if scenario == "steady" and product.stock_quantity <= 25:
                base_weight *= 1.2
            weights.append(max(base_weight, 0.1))
        return self._random.choices(products, weights=weights, k=1)[0]

    def _pick_quantity(self, product: Product, scenario: str) -> int:
        """Choose mostly single-item orders, reserving larger bursts for scarcity scenarios."""
        category = product.category
        roll = self._random.random()
        if scenario == "scarcity":
            if category == "Electronics":
                return 2 if roll < 0.55 else 3
            return 2 if roll < 0.75 else 3
        if category == "Electronics" and self._random.random() < 0.15:
            return 2 if roll < 0.8 else 3
        if roll < 0.78:
            return 1
        if roll < 0.94:
            return 2
        return 3


async def main() -> None:
    """Entrypoint for the long-running demand simulator."""
    simulator = DemandSimulator()
    await simulator.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Demand simulator stopped.")

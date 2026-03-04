"""Order-driven inventory update service."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import AsyncSessionLocal, init_db
from app.models import OrderEvent, Product
from shared.kafka_utils import AsyncKafkaConsumer, AsyncKafkaProducer

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [inventory-service] %(message)s",
)
logger = logging.getLogger(__name__)


class InventoryService:
    """Consumes orders, updates stock, and emits downstream inventory events."""

    def __init__(self) -> None:
        self._consumer = AsyncKafkaConsumer(
            "orders",
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.inventory_consumer_group,
            enable_auto_commit=False,
        )
        self._producer = AsyncKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)

    async def run(self) -> None:
        """Start Kafka clients and process order events forever."""
        await init_db()
        await self._producer.start()
        await self._consumer.start()
        logger.info(
            "Inventory service started. Consumer group=%s low_stock_threshold=%s",
            settings.inventory_consumer_group,
            settings.low_stock_threshold,
        )
        try:
            async for message in self._consumer.messages():
                await self._handle_order_event(message["value"])
                await self._consumer.commit()
        finally:
            await self._consumer.stop()
            await self._producer.stop()

    async def _handle_order_event(self, event: dict[str, object]) -> None:
        """Apply one order event to product inventory and emit downstream events."""
        if event.get("_invalid_json"):
            logger.warning("Skipping invalid order payload: %s", event.get("_raw"))
            return

        product_id = int(event["product_id"])
        quantity = int(event["quantity"])
        timestamp = datetime.now(UTC)

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()
            if product is None:
                logger.warning("Received order for unknown product_id=%s. Event skipped.", product_id)
                return

            previous_stock = product.stock_quantity
            new_stock = max(previous_stock - quantity, 0)
            product.stock_quantity = new_stock
            session.add(
                OrderEvent(
                    event_id=str(event.get("event_id")),
                    product_id=product_id,
                    quantity=quantity,
                    customer_region=str(event.get("customer_region", "unknown")),
                    created_at=datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00")),
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.warning("Duplicate order event ignored: event_id=%s", event.get("event_id"))
                return

        inventory_event = {
            "event_id": str(uuid4()),
            "product_id": product_id,
            "previous_stock": previous_stock,
            "new_stock": new_stock,
            "change_reason": "ORDER",
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        }
        await self._producer.send("inventory-updates", inventory_event, key=str(product_id))

        logger.info(
            "Processed order: product_id=%s quantity=%s stock %s -> %s",
            product_id,
            quantity,
            previous_stock,
            new_stock,
        )

        if new_stock < settings.low_stock_threshold:
            alert_event = {
                "event_id": str(uuid4()),
                "product_id": product_id,
                "alert_type": "LOW_STOCK",
                "current_stock": new_stock,
                "threshold": settings.low_stock_threshold,
                "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            }
            await self._producer.send("alerts", alert_event, key=str(product_id))
            logger.warning(
                "Published low stock alert: product_id=%s current_stock=%s threshold=%s",
                product_id,
                new_stock,
                settings.low_stock_threshold,
            )


async def main() -> None:
    """Entrypoint for the long-running inventory service."""
    service = InventoryService()
    await service.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Inventory service stopped.")

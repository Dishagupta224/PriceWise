"""Background Kafka consumer that forwards live events to WebSocket rooms."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from shared.kafka_utils import AsyncKafkaConsumer

from app.config import get_settings
from app.websocket_manager import WebSocketManager

settings = get_settings()
logger = logging.getLogger(__name__)

TOPIC_TO_EVENT_TYPE = {
    "price-changes": "PRICE_CHANGE",
    "price-decisions": "AGENT_DECISION",
    "alerts": "ALERT",
}


class KafkaWebSocketBridge:
    """Consume Kafka events in the background and broadcast them to WebSocket clients."""

    def __init__(self, manager: WebSocketManager) -> None:
        self._manager = manager
        self._task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        """Start the bridge loop once for the application lifespan."""
        if self._task is not None and not self._task.done():
            return
        self._shutdown.clear()
        self._task = asyncio.create_task(self._run(), name="dashboard-kafka-websocket-bridge")

    async def stop(self) -> None:
        """Stop the bridge and wait for the worker to exit."""
        self._shutdown.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        """Restart the consumer loop on transient failures."""
        while not self._shutdown.is_set():
            consumer = AsyncKafkaConsumer(
                "price-decisions",
                "price-changes",
                "alerts",
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id="dashboard-api-live-bridge",
                auto_offset_reset="latest",
                enable_auto_commit=True,
            )
            try:
                await consumer.start()
                logger.info("Dashboard Kafka bridge started.")
                async for message in consumer.messages():
                    if self._shutdown.is_set():
                        break
                    await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Dashboard Kafka bridge failed. Restarting in 3s.")
                await asyncio.sleep(3)
            finally:
                await consumer.stop()

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Transform one Kafka event into a WebSocket broadcast message."""
        topic = str(message["topic"])
        event_type = TOPIC_TO_EVENT_TYPE.get(topic)
        if event_type is None:
            return

        data = message["value"]
        if not isinstance(data, dict) or data.get("_invalid_json"):
            return

        timestamp = (
            str(data.get("created_at") or data.get("timestamp"))
            if data.get("created_at") or data.get("timestamp")
            else datetime.now(UTC).isoformat().replace("+00:00", "Z")
        )
        envelope = {
            "type": event_type,
            "data": data,
            "timestamp": timestamp,
        }

        rooms = {"live-feed"}
        product_id = data.get("product_id")
        if product_id is not None:
            rooms.add(f"product:{product_id}")
        await self._manager.broadcast(rooms, envelope)

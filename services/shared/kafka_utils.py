"""Reusable async Kafka producer and consumer utilities."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, UnknownTopicOrPartitionError

logger = logging.getLogger(__name__)


def json_serializer(value: Any) -> bytes:
    """Serialize Python data into UTF-8 JSON bytes."""
    return json.dumps(value, default=str).encode("utf-8")


def json_deserializer(value: bytes | None) -> Any:
    """Deserialize UTF-8 JSON bytes into Python data."""
    if value is None:
        return None
    decoded = value.decode("utf-8")
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        logger.warning("Received invalid JSON payload from Kafka: %s", decoded)
        return {"_invalid_json": True, "_raw": decoded}


class KafkaConnectionMixin:
    """Shared retry behavior for Kafka clients."""

    def __init__(
        self,
        bootstrap_servers: str = "kafka:9092",
        retry_attempts: int = 10,
        retry_delay_seconds: float = 3.0,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds

    async def _start_with_retry(self, start_callback: Callable[[], Awaitable[None]], client_name: str) -> None:
        """Start a Kafka client with bounded retries."""
        for attempt in range(1, self.retry_attempts + 1):
            try:
                await start_callback()
                logger.info("%s connected to Kafka at %s", client_name, self.bootstrap_servers)
                return
            except (KafkaConnectionError, UnknownTopicOrPartitionError):
                if attempt == self.retry_attempts:
                    logger.exception("%s failed to connect to Kafka after %s attempts", client_name, attempt)
                    raise
                logger.warning(
                    "%s could not connect to Kafka (attempt %s/%s). Retrying in %.1fs.",
                    client_name,
                    attempt,
                    self.retry_attempts,
                    self.retry_delay_seconds,
                )
                await asyncio.sleep(self.retry_delay_seconds)


class AsyncKafkaProducer(KafkaConnectionMixin):
    """Async producer with JSON serialization and graceful shutdown."""

    def __init__(
        self,
        bootstrap_servers: str = "kafka:9092",
        retry_attempts: int = 10,
        retry_delay_seconds: float = 3.0,
    ) -> None:
        super().__init__(bootstrap_servers, retry_attempts, retry_delay_seconds)
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=json_serializer,
        )

    async def start(self) -> None:
        """Start the producer."""
        await self._start_with_retry(self._producer.start, "Kafka producer")

    async def stop(self) -> None:
        """Stop the producer without surfacing shutdown noise."""
        with suppress(Exception):
            await self._producer.stop()

    async def send(self, topic: str, value: Any, key: str | None = None) -> None:
        """Publish one message to a topic."""
        encoded_key = key.encode("utf-8") if key is not None else None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                await self._producer.send_and_wait(topic, value=value, key=encoded_key)
                return
            except UnknownTopicOrPartitionError:
                if attempt == self.retry_attempts:
                    logger.exception("Producer could not publish to topic %s after %s attempts", topic, attempt)
                    raise
                logger.warning(
                    "Producer topic %s not ready yet (attempt %s/%s). Retrying in %.1fs.",
                    topic,
                    attempt,
                    self.retry_attempts,
                    self.retry_delay_seconds,
                )
                await asyncio.sleep(self.retry_delay_seconds)

    async def __aenter__(self) -> "AsyncKafkaProducer":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()


class AsyncKafkaConsumer(KafkaConnectionMixin):
    """Async consumer with JSON decoding and graceful shutdown."""

    def __init__(
        self,
        *topics: str,
        bootstrap_servers: str = "kafka:9092",
        group_id: str,
        auto_offset_reset: str = "earliest",
        retry_attempts: int = 10,
        retry_delay_seconds: float = 3.0,
        enable_auto_commit: bool = True,
    ) -> None:
        super().__init__(bootstrap_servers, retry_attempts, retry_delay_seconds)
        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=enable_auto_commit,
            value_deserializer=json_deserializer,
        )

    async def start(self) -> None:
        """Start the consumer."""
        await self._start_with_retry(self._consumer.start, "Kafka consumer")

    async def stop(self) -> None:
        """Stop the consumer without surfacing shutdown noise."""
        with suppress(Exception):
            await self._consumer.stop()

    async def commit(self) -> None:
        """Commit the current consumed offsets."""
        await self._consumer.commit()

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded Kafka messages plus metadata."""
        async for message in self._consumer:
            yield {
                "topic": message.topic,
                "partition": message.partition,
                "offset": message.offset,
                "key": message.key.decode("utf-8") if message.key else None,
                "timestamp": message.timestamp,
                "value": message.value,
            }

    async def __aenter__(self) -> "AsyncKafkaConsumer":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

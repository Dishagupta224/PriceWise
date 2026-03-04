"""Pricing agent runtime: Kafka consumer, bounded processing queue, metrics, and graceful shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agent import PricingDecisionAgent
from app.config import get_settings
from app.models import Base
from app.rule_engine import RuleDecision, RuleEngine
from shared.database import AsyncSessionLocal, engine
from shared.kafka_utils import AsyncKafkaConsumer, AsyncKafkaProducer

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [pricing-agent] %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PricingMetrics:
    """Lightweight in-memory counters for observability."""

    events_received: int = 0
    events_processed: int = 0
    events_ignored: int = 0
    decisions_made: int = 0
    total_decision_seconds: float = 0.0

    @property
    def avg_decision_time(self) -> float:
        """Return the running average agent-decision time."""
        if self.decisions_made == 0:
            return 0.0
        return self.total_decision_seconds / self.decisions_made


class PricingAgentService:
    """Consume pricing signals, apply fast-path rules, and route eligible events to the AI agent."""

    def __init__(self) -> None:
        self._rule_engine = RuleEngine()
        self._agent = PricingDecisionAgent()
        self._consumer = AsyncKafkaConsumer(
            "price-changes",
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id="pricing-agent-fast-path",
            enable_auto_commit=False,
        )
        self._producer = AsyncKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        self._queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=settings.processing_queue_size)
        self._shutdown_event = asyncio.Event()
        self._metrics = PricingMetrics()
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._metrics_task: asyncio.Task[None] | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._health_path = Path(settings.healthcheck_file)
        self._cleanup_started = False

    async def run(self) -> None:
        """Start Kafka clients, worker tasks, and process events until shutdown is requested."""
        await init_db()
        await self._producer.start()
        await self._consumer.start()
        self._install_signal_handlers()
        self._worker_tasks = [
            asyncio.create_task(self._worker(worker_id), name=f"pricing-agent-worker-{worker_id}")
            for worker_id in range(1, settings.max_concurrent_decisions + 1)
        ]
        self._metrics_task = asyncio.create_task(self._log_metrics_loop(), name="pricing-agent-metrics")
        self._health_task = asyncio.create_task(self._healthbeat_loop(), name="pricing-agent-health")

        logger.info(
            "Pricing agent started. topic=price-changes consumer_group=pricing-agent-fast-path concurrency=%s queue_size=%s",
            settings.max_concurrent_decisions,
            settings.processing_queue_size,
        )
        logger.info("Fast path and GPT smart path are active. If OPENAI_API_KEY is missing, the agent will safely HOLD.")

        messages = self._consumer.messages()
        try:
            while not self._shutdown_event.is_set():
                next_message_task = asyncio.create_task(anext(messages), name="pricing-agent-consumer-next")
                shutdown_task = asyncio.create_task(self._shutdown_event.wait(), name="pricing-agent-shutdown-wait")
                done, pending = await asyncio.wait(
                    {next_message_task, shutdown_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if shutdown_task in done:
                    next_message_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await next_message_task
                    break

                shutdown_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await shutdown_task

                try:
                    message = next_message_task.result()
                except StopAsyncIteration:
                    break

                event = message["value"]
                self._metrics.events_received += 1

                if event.get("_invalid_json"):
                    logger.warning("Skipping invalid price-change payload: %s", event.get("_raw"))
                    self._metrics.events_ignored += 1
                    await self._consumer.commit()
                    continue

                await self._queue.put(event)
                await self._consumer.commit()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Stop accepting new work, finish queued work, and tear down resources cleanly."""
        if self._cleanup_started:
            return

        self._cleanup_started = True
        self._shutdown_event.set()
        logger.info("Shutdown requested. Waiting for queued pricing events to finish.")

        await self._consumer.stop()
        await self._queue.join()

        for _ in self._worker_tasks:
            await self._queue.put({})

        for task in self._worker_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        for task in (self._metrics_task, self._health_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        await self._producer.stop()
        self._cleanup_healthcheck_file()
        logger.info(
            "Pricing agent stopped. processed=%s ignored=%s decisions=%s avg_decision_time=%.2fs",
            self._metrics.events_processed,
            self._metrics.events_ignored,
            self._metrics.decisions_made,
            self._metrics.avg_decision_time,
        )

    async def _worker(self, worker_id: int) -> None:
        """Process queued events up to the configured concurrency limit."""
        while True:
            event = await self._queue.get()
            try:
                if not event:
                    return
                await self._process_event(event, worker_id)
            finally:
                self._queue.task_done()

    async def _process_event(self, event: dict[str, object], worker_id: int) -> None:
        """Run the full pipeline for one price-change event."""
        product_id = event.get("product_id")
        logger.info("Worker %s received event for product_id=%s event_id=%s", worker_id, product_id, event.get("event_id"))

        async with AsyncSessionLocal() as session:
            evaluation = await self._rule_engine.evaluate(event, session)

        logger.info(
            "Pipeline step rule-engine: product_id=%s decision=%s reason=%s",
            product_id,
            evaluation.decision.value,
            evaluation.reason,
        )

        if evaluation.decision is RuleDecision.IGNORE:
            self._metrics.events_ignored += 1
            return

        if evaluation.decision is RuleDecision.DIRECT_ACTION:
            if evaluation.direct_topic and evaluation.direct_payload:
                await self._producer.send(evaluation.direct_topic, evaluation.direct_payload, key=str(product_id))
            self._metrics.events_processed += 1
            self._metrics.decisions_made += 1
            logger.warning(
                "Pipeline action direct: product_id=%s topic=%s reason=%s",
                product_id,
                evaluation.direct_topic,
                evaluation.reason,
            )
            return

        started = time.perf_counter()
        result = await self._agent.process_event(event)
        decision_seconds = time.perf_counter() - started

        await self._producer.send("price-decisions", result.to_kafka_payload(int(product_id)), key=str(product_id))
        if result.alert_payload is not None:
            await self._producer.send("alerts", result.alert_payload, key=str(product_id))

        self._metrics.events_processed += 1
        self._metrics.decisions_made += 1
        self._metrics.total_decision_seconds += decision_seconds

        logger.info(
            "Pipeline completed: product_id=%s rule=%s agent_decision=%s execution_status=%s action_time=%.2fs",
            product_id,
            evaluation.decision.value,
            result.decision_type.value,
            result.execution_status.value,
            decision_seconds,
        )

    async def _log_metrics_loop(self) -> None:
        """Emit periodic metrics while the service is running."""
        while True:
            await asyncio.sleep(settings.metrics_log_interval_seconds)
            logger.info(
                "Metrics: events_received=%s events_processed=%s events_ignored=%s decisions_made=%s avg_decision_time=%.2fs queue_depth=%s",
                self._metrics.events_received,
                self._metrics.events_processed,
                self._metrics.events_ignored,
                self._metrics.decisions_made,
                self._metrics.avg_decision_time,
                self._queue.qsize(),
            )

    async def _healthbeat_loop(self) -> None:
        """Continuously refresh a healthcheck heartbeat file while the service is alive."""
        self._health_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            self._health_path.write_text("ok", encoding="utf-8")
            await asyncio.sleep(10)

    def _install_signal_handlers(self) -> None:
        """Request graceful shutdown on SIGINT/SIGTERM."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._shutdown_event.set)

    def _cleanup_healthcheck_file(self) -> None:
        """Remove the heartbeat file on shutdown."""
        with contextlib.suppress(FileNotFoundError):
            self._health_path.unlink()


async def init_db() -> None:
    """Create any pricing-agent-owned tables that do not yet exist."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def main() -> None:
    """Entrypoint for the pricing agent service."""
    service = PricingAgentService()
    await service.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Pricing agent stopped.")

"""Connection manager for dashboard WebSocket clients."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClientConnection:
    """State tracked for one connected dashboard client."""

    connection_id: str
    websocket: WebSocket
    rooms: set[str]
    queue: asyncio.Queue[dict[str, object]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=settings.websocket_queue_size)
    )
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    last_pong_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sender_task: asyncio.Task[None] | None = None
    receiver_task: asyncio.Task[None] | None = None
    heartbeat_task: asyncio.Task[None] | None = None


class WebSocketManager:
    """Manage connected clients, room subscriptions, and heartbeats."""

    def __init__(self) -> None:
        self._clients: dict[str, ClientConnection] = {}
        self._rooms: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, rooms: set[str]) -> ClientConnection:
        """Accept a client and register it in the requested rooms."""
        await websocket.accept()
        connection = ClientConnection(connection_id=str(uuid4()), websocket=websocket, rooms=set(rooms))
        async with self._lock:
            self._clients[connection.connection_id] = connection
            for room in rooms:
                self._rooms.setdefault(room, set()).add(connection.connection_id)

        connection.sender_task = asyncio.create_task(self._sender_loop(connection), name=f"ws-sender-{connection.connection_id}")
        connection.receiver_task = asyncio.create_task(
            self._receiver_loop(connection),
            name=f"ws-receiver-{connection.connection_id}",
        )
        connection.heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(connection),
            name=f"ws-heartbeat-{connection.connection_id}",
        )

        await self._enqueue(
            connection,
            {
                "type": "CONNECTED",
                "data": {"rooms": sorted(connection.rooms), "connection_id": connection.connection_id},
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
        )
        return connection

    async def wait_until_closed(self, connection: ClientConnection) -> None:
        """Block until a client disconnects."""
        await connection.closed.wait()

    async def disconnect(self, connection_id: str) -> None:
        """Remove a client and stop its background tasks."""
        async with self._lock:
            connection = self._clients.pop(connection_id, None)
            if connection is None:
                return
            for room in connection.rooms:
                members = self._rooms.get(room)
                if members is None:
                    continue
                members.discard(connection_id)
                if not members:
                    self._rooms.pop(room, None)

        if connection.closed.is_set():
            return
        connection.closed.set()
        for task in (connection.sender_task, connection.receiver_task, connection.heartbeat_task):
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        with contextlib.suppress(Exception):
            await connection.websocket.close()

    async def broadcast(self, rooms: set[str], message: dict[str, object]) -> None:
        """Fan out a message to all clients subscribed to any of the provided rooms."""
        async with self._lock:
            target_ids = {client_id for room in rooms for client_id in self._rooms.get(room, set())}
            targets = [self._clients[client_id] for client_id in target_ids if client_id in self._clients]

        for connection in targets:
            await self._enqueue(connection, message)

    async def shutdown(self) -> None:
        """Disconnect all clients during API shutdown."""
        async with self._lock:
            client_ids = list(self._clients.keys())
        for client_id in client_ids:
            await self.disconnect(client_id)

    async def _enqueue(self, connection: ClientConnection, message: dict[str, object]) -> None:
        """Queue a message for one client, disconnecting slow readers when necessary."""
        try:
            connection.queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Disconnecting slow WebSocket client %s due to backpressure.", connection.connection_id)
            await self.disconnect(connection.connection_id)

    async def _sender_loop(self, connection: ClientConnection) -> None:
        """Serialize queued messages onto the socket."""
        try:
            while not connection.closed.is_set():
                payload = await connection.queue.get()
                await connection.websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            logger.info("WebSocket sender closed for client %s", connection.connection_id)
        finally:
            await self.disconnect(connection.connection_id)

    async def _receiver_loop(self, connection: ClientConnection) -> None:
        """Receive client messages so disconnects and heartbeats are observed."""
        try:
            while not connection.closed.is_set():
                message = await connection.websocket.receive()
                message_type = message.get("type")
                if message_type == "websocket.disconnect":
                    break
                if message_type != "websocket.receive":
                    continue
                text = message.get("text")
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = {"type": text}
                payload_type = str(payload.get("type", "")).upper()
                if payload_type in {"PONG", "PING"}:
                    connection.last_pong_at = datetime.now(UTC)
                    if payload_type == "PING":
                        await self._enqueue(
                            connection,
                            {
                                "type": "PONG",
                                "data": {},
                                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                            },
                        )
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.info("WebSocket receiver closed for client %s", connection.connection_id)
        finally:
            await self.disconnect(connection.connection_id)

    async def _heartbeat_loop(self, connection: ClientConnection) -> None:
        """Send heartbeat pings and drop dead sockets."""
        try:
            while not connection.closed.is_set():
                await asyncio.sleep(settings.websocket_ping_interval_seconds)
                age = (datetime.now(UTC) - connection.last_pong_at).total_seconds()
                if age > settings.websocket_pong_timeout_seconds:
                    logger.warning("WebSocket client %s timed out waiting for heartbeat.", connection.connection_id)
                    break
                await self._enqueue(
                    connection,
                    {
                        "type": "PING",
                        "data": {},
                        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    },
                )
        finally:
            await self.disconnect(connection.connection_id)

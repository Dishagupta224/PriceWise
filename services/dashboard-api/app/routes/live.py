"""WebSocket endpoints for dashboard live feeds."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.websocket_manager import WebSocketManager

router = APIRouter(tags=["live"])


def create_live_router(manager: WebSocketManager) -> APIRouter:
    """Build a router bound to the application WebSocket manager."""

    @router.websocket("/ws/live-feed")
    async def live_feed(websocket: WebSocket) -> None:
        connection = await manager.connect(websocket, {"live-feed"})
        await manager.wait_until_closed(connection)

    @router.websocket("/ws/product/{product_id}")
    async def product_feed(websocket: WebSocket, product_id: int) -> None:
        connection = await manager.connect(websocket, {f"product:{product_id}"})
        await manager.wait_until_closed(connection)

    return router

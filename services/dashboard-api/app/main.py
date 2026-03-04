"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.kafka_websocket_bridge import KafkaWebSocketBridge
from app.routes.live import create_live_router
from app.routes.dashboard import router as dashboard_router
from app.routes.products import router as products_router
from app.seed import init_db
from app.websocket_manager import WebSocketManager

settings = get_settings()
websocket_manager = WebSocketManager()
live_bridge = KafkaWebSocketBridge(websocket_manager)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create database tables during service startup."""
    await init_db()
    await live_bridge.start()
    yield
    await live_bridge.stop()
    await websocket_manager.shutdown()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Simple health endpoint for container orchestration."""
    return {"status": "ok"}


app.include_router(products_router, prefix="/api")
app.include_router(products_router, prefix="/api/v1")
app.include_router(products_router)
app.include_router(dashboard_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(dashboard_router)
app.include_router(create_live_router(websocket_manager))

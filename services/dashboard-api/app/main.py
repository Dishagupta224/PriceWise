"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.kafka_websocket_bridge import KafkaWebSocketBridge
from app.routes.live import create_live_router
from app.routes.runtime_session import router as runtime_session_router
from app.routes.dashboard import router as dashboard_router
from app.routes.products import router as products_router
from app.seed import init_db
from app.websocket_manager import WebSocketManager
from shared.observability import clear_request_id, configure_logging, set_request_id

settings = get_settings()
configure_logging("dashboard-api", settings.log_level)
logger = logging.getLogger(__name__)
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach request ID to every HTTP request/response cycle."""
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    set_request_id(request_id)
    try:
        response = await call_next(request)
    except Exception:
        clear_request_id()
        raise
    response.headers["x-request-id"] = request_id
    clear_request_id()
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured 500 responses with request IDs."""
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception("Unhandled request error path=%s request_id=%s", request.url.path, request_id)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Simple health endpoint for container orchestration."""
    return {"status": "ok"}


app.include_router(products_router, prefix="/api")
app.include_router(products_router, prefix="/api/v1")
app.include_router(products_router)
app.include_router(runtime_session_router, prefix="/api")
app.include_router(runtime_session_router, prefix="/api/v1")
app.include_router(runtime_session_router)
app.include_router(dashboard_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(dashboard_router)
app.include_router(create_live_router(websocket_manager))

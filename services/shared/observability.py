"""Shared observability helpers: JSON logging, request IDs, and healthbeats."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

_REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonLogFormatter(logging.Formatter):
    """Render log records as JSON lines."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self._service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service_name: str, log_level: str = "INFO") -> None:
    """Configure root logger to emit JSON logs consistently."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter(service_name))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def set_request_id(request_id: str | None) -> None:
    """Bind request ID to current execution context."""
    _REQUEST_ID_CTX.set(request_id)


def get_request_id() -> str | None:
    """Return current request ID."""
    return _REQUEST_ID_CTX.get()


def clear_request_id() -> None:
    """Clear request ID from current execution context."""
    _REQUEST_ID_CTX.set(None)


def ensure_request_id(payload: dict[str, Any], *, source_key: str = "event_id") -> str:
    """Ensure payload has a request ID and return it."""
    existing = payload.get("request_id")
    if isinstance(existing, str) and existing.strip():
        request_id = existing.strip()
    else:
        source_event = payload.get(source_key)
        if isinstance(source_event, str) and source_event.strip():
            request_id = source_event.strip()
        else:
            request_id = str(uuid4())
        payload["request_id"] = request_id
    set_request_id(request_id)
    return request_id


def touch_healthcheck(path: str) -> None:
    """Update service heartbeat file used by container healthchecks."""
    health_path = Path(path)
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text("ok", encoding="utf-8")

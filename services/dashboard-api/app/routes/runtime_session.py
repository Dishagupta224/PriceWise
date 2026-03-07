"""Routes for automatic runtime activation on dashboard visits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import RuntimeAccessSession
from app.schemas import RuntimeSessionStatusResponse

router = APIRouter(prefix="/runtime-session", tags=["runtime-session"])

SESSION_DURATION_MINUTES = 8
MAX_ACTIVATIONS_PER_DAY = 15
RUNTIME_START_LOCK_ID = 947321


def _get_user_id(x_user_id: str | None) -> str:
    """Validate and normalize the caller identifier."""
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing x-user-id header.")
    if len(user_id) > 128:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="x-user-id is too long.")
    return user_id


async def _build_status(session: AsyncSession, user_id: str, now: datetime) -> RuntimeSessionStatusResponse:
    """Construct runtime status and global daily quota numbers."""
    active_expires_at = (
        await session.execute(
            select(func.max(RuntimeAccessSession.expires_at)).where(RuntimeAccessSession.expires_at > now)
        )
    ).scalar_one_or_none()
    active = active_expires_at is not None

    day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    used_today = int(
        (
            await session.execute(
                select(func.count())
                .select_from(RuntimeAccessSession)
                .where(
                    RuntimeAccessSession.activated_at >= day_start,
                    RuntimeAccessSession.activated_at < day_end,
                )
            )
        ).scalar_one()
    )
    remaining = max(0, MAX_ACTIVATIONS_PER_DAY - used_today)

    message = None
    if active:
        message = "Runtime is active. Simulators and AI pipeline are enabled."
    elif remaining == 0:
        message = "Global daily limit reached. Runtime will reset tomorrow."
    else:
        message = "Runtime inactive. Visit refresh starts an 8-minute session."

    return RuntimeSessionStatusResponse(
        active=active,
        expires_at=active_expires_at,
        activations_used_today=used_today,
        activations_limit_per_day=MAX_ACTIVATIONS_PER_DAY,
        activations_remaining_today=remaining,
        message=message,
    )


async def _acquire_runtime_start_lock(session: AsyncSession) -> None:
    """Serialize session-start requests to prevent overlap on parallel tab loads."""
    connection = await session.connection()
    if connection.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": RUNTIME_START_LOCK_ID},
        )


@router.get("/status", response_model=RuntimeSessionStatusResponse)
async def get_runtime_status(
    session: AsyncSession = Depends(get_db_session),
    x_user_id: str | None = Header(default=None),
) -> RuntimeSessionStatusResponse:
    """Return runtime status without changing quota."""
    user_id = _get_user_id(x_user_id)
    return await _build_status(session, user_id, datetime.now(UTC))


@router.post("/start", response_model=RuntimeSessionStatusResponse)
async def start_runtime_session(
    session: AsyncSession = Depends(get_db_session),
    x_user_id: str | None = Header(default=None),
) -> RuntimeSessionStatusResponse:
    """Start a runtime session when needed and global quota allows."""
    user_id = _get_user_id(x_user_id)
    async with session.begin():
        await _acquire_runtime_start_lock(session)
        now = datetime.now(UTC)
        status_payload = await _build_status(session, user_id, now)

        if status_payload.active:
            return status_payload

        if status_payload.activations_remaining_today <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Global daily runtime activation limit reached.",
            )

        session.add(
            RuntimeAccessSession(
                user_id=user_id,
                activated_at=now,
                expires_at=now + timedelta(minutes=SESSION_DURATION_MINUTES),
            )
        )
    await session.commit()
    return await _build_status(session, user_id, datetime.now(UTC))

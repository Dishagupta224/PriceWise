"""Shared async SQLAlchemy engine and session helpers."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://smart_pricing:smart_pricing@postgres:5432/smart_pricing",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Declarative base shared by service-specific ORM models."""


async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Yield a reusable async database session."""
    async with AsyncSessionLocal() as session:
        yield session

"""Async database setup for the inventory service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Declarative base for local ORM models."""


async def init_db() -> None:
    """Create any inventory-service-owned tables that do not yet exist."""
    from app.models import Base as ModelBase

    async with engine.begin() as connection:
        await connection.run_sync(ModelBase.metadata.create_all)

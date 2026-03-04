"""Subset of models needed for stock updates and persisted order history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    """Product row updated by the inventory service."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OrderEvent(Base):
    """Persisted order event for downstream demand-trend analysis."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    product_id: Mapped[int] = mapped_column(nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    customer_region: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

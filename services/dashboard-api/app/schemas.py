"""Pydantic schemas for request and response payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import AgentDecisionType, DecisionActor, ExecutionStatus


class ORMBaseSchema(BaseModel):
    """Base schema configured for SQLAlchemy model serialization."""

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    """Shared product fields with business validation."""

    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = None
    our_price: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
    cost_price: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
    stock_quantity: int = Field(ge=0)
    min_margin_percent: float = Field(default=20.0, ge=0, le=100)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_margin(self) -> "ProductBase":
        """Ensure prices respect the configured minimum margin."""
        margin_multiplier = Decimal("1") + (Decimal(str(self.min_margin_percent)) / Decimal("100"))
        minimum_price = self.cost_price * margin_multiplier
        if self.our_price < minimum_price:
            raise ValueError("our_price must satisfy the configured minimum margin percent.")
        return self

    @field_validator("name", "category", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        """Normalize required text fields."""
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        """Normalize optional text fields."""
        if isinstance(value, str):
            value = value.strip()
        return value


class ProductCreate(ProductBase):
    """Payload for creating a product."""


class ProductUpdate(BaseModel):
    """Payload for updating a product."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    our_price: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=10)
    cost_price: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=10)
    stock_quantity: int | None = Field(default=None, ge=0)
    min_margin_percent: float | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None

    @field_validator("name", "category", mode="before")
    @classmethod
    def strip_optional_required_text(cls, value: object) -> object:
        """Normalize optional text fields."""
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        """Normalize optional description."""
        if isinstance(value, str):
            value = value.strip()
        return value


class CompetitorPriceBase(BaseModel):
    """Shared competitor price fields."""

    product_id: int = Field(gt=0)
    competitor_name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0, decimal_places=2, max_digits=10)


class CompetitorPriceCreate(CompetitorPriceBase):
    """Payload for storing a competitor price snapshot."""


class CompetitorPriceRead(ORMBaseSchema, CompetitorPriceBase):
    """Competitor price response payload."""

    id: int
    captured_at: datetime


class PriceHistoryBase(BaseModel):
    """Shared price history fields."""

    product_id: int = Field(gt=0)
    old_price: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
    new_price: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
    change_reason: str = Field(min_length=1)
    decided_by: DecisionActor


class PriceHistoryCreate(PriceHistoryBase):
    """Payload for recording a price change."""


class PriceHistoryRead(ORMBaseSchema, PriceHistoryBase):
    """Price history response payload."""

    id: int
    created_at: datetime


class AgentDecisionBase(BaseModel):
    """Shared agent decision fields."""

    product_id: int = Field(gt=0)
    decision_type: AgentDecisionType
    reasoning: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)
    tools_used: list[Any] = Field(default_factory=list)
    execution_status: ExecutionStatus


class AgentDecisionCreate(AgentDecisionBase):
    """Payload for storing an agent decision."""


class AgentDecisionRead(ORMBaseSchema, AgentDecisionBase):
    """Agent decision response payload."""

    id: int
    created_at: datetime


class ProductRead(ORMBaseSchema, ProductBase):
    """Product response payload."""

    id: int
    created_at: datetime
    updated_at: datetime
    competitor_prices: list[CompetitorPriceRead] = Field(default_factory=list)
    price_history: list[PriceHistoryRead] = Field(default_factory=list)
    agent_decisions: list[AgentDecisionRead] = Field(default_factory=list)


class PaginationMeta(BaseModel):
    """Common pagination metadata."""

    page: int
    page_size: int
    total_items: int
    total_pages: int


class CompetitorSnapshot(BaseModel):
    """Latest competitor snapshot for a product."""

    competitor_name: str
    price: Decimal
    captured_at: datetime


class ProductListItem(ORMBaseSchema):
    """Compact enriched product row for the dashboard grid."""

    id: int
    name: str
    category: str
    description: str | None = None
    our_price: Decimal
    cost_price: Decimal
    stock_quantity: int
    min_margin_percent: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
    current_margin_percent: float
    price_change_24h: float
    latest_competitor_prices: list[CompetitorSnapshot] = Field(default_factory=list)


class ProductDetailResponse(ProductListItem):
    """Expanded product detail response."""

    competitor_prices: list[CompetitorPriceRead] = Field(default_factory=list)


class PriceHistoryPoint(BaseModel):
    """One point in the rendered chart time series."""

    timestamp: datetime
    our_price: Decimal | None = None
    competitor_name: str | None = None
    competitor_price: Decimal | None = None


class ProductPriceHistoryResponse(BaseModel):
    """Chart-friendly price history payload."""

    product_id: int
    product_name: str
    days: int
    points: list[PriceHistoryPoint]


class DecisionListItem(BaseModel):
    """Summary row for recent agent decisions."""

    id: int
    product_id: int
    product_name: str
    decision_type: AgentDecisionType
    execution_status: ExecutionStatus
    confidence_score: float
    reasoning_preview: str
    created_at: datetime


class DecisionDetailResponse(BaseModel):
    """Full agent decision detail for drill-down views."""

    id: int
    product_id: int
    product_name: str
    decision_type: AgentDecisionType
    execution_status: ExecutionStatus
    confidence_score: float
    reasoning: str
    tools_used: list[Any] = Field(default_factory=list)
    before_price: Decimal | None = None
    after_price: Decimal | None = None
    created_at: datetime


class AnalyticsSummaryResponse(BaseModel):
    """Top-line dashboard metrics."""

    total_active_products: int
    total_decisions_today: int
    avg_margin_percent: float
    total_revenue_impact: Decimal
    products_needing_attention: int
    low_stock_products: int
    overpriced_products: int


class TopMoverItem(BaseModel):
    """Biggest recent product price move."""

    product_id: int
    product_name: str
    old_price: Decimal
    new_price: Decimal
    percentage_change: float
    direction: str
    reason: str
    created_at: datetime


class TopMoversResponse(BaseModel):
    """Recent biggest product price moves."""

    items: list[TopMoverItem]


class PaginatedProductsResponse(BaseModel):
    """Paginated product list response."""

    items: list[ProductListItem]
    pagination: PaginationMeta


class PaginatedDecisionsResponse(BaseModel):
    """Paginated decision list response."""

    items: list[DecisionListItem]
    pagination: PaginationMeta


class RuntimeSessionStatusResponse(BaseModel):
    """Runtime session status for the current user and daily quota usage."""

    active: bool
    expires_at: datetime | None = None
    activations_used_today: int
    activations_limit_per_day: int
    activations_remaining_today: int
    message: str | None = None

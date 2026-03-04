"""Enums used by the pricing agent service."""

from enum import StrEnum


class DecisionActor(StrEnum):
    """Originator of a price change."""

    AGENT = "AGENT"
    MANUAL = "MANUAL"


class AgentDecisionType(StrEnum):
    """High-level actions the pricing agent can take."""

    PRICE_DROP = "PRICE_DROP"
    PRICE_HOLD = "PRICE_HOLD"
    PRICE_INCREASE = "PRICE_INCREASE"
    REORDER_ALERT = "REORDER_ALERT"


class ExecutionStatus(StrEnum):
    """Execution state for an agent decision."""

    EXECUTED = "EXECUTED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"

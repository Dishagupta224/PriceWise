"""Core GPT-powered pricing agent with tool calling and safe execution fallbacks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from sqlalchemy import select

from app.agent_tools import (
    OPENAI_TOOL_FUNCTIONS,
    OPENAI_TOOL_SCHEMAS,
    get_demand_trend,
    get_market_position,
    get_product_details,
    update_product_price,
)
from app.config import get_settings
from app.enums import AgentDecisionType, ExecutionStatus
from app.models import AgentDecision, RuntimeAccessSession
from shared.database import AsyncSessionLocal

settings = get_settings()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an intelligent e-commerce pricing agent. Your job is to analyze market events and make optimal pricing decisions that maximize profit while staying competitive. You have access to tools to check product details, competitor prices, demand trends, margins, and price history.

RULES:
1. Never set a price below the minimum margin threshold
2. Don't react to every small competitor change - be strategic
3. Consider demand trends - if demand is high, you may not need to drop price even if competitors are cheaper
4. If stock is low (<20 units) and demand is high, consider INCREASING price (scarcity pricing)
5. Always explain your reasoning clearly
6. HOLD is a last resort. If there is a clear safe price change supported by market data, prefer acting over holding.
7. If competitors are significantly more expensive than us, demand is stable or rising, and stock is healthy, consider a strategic PRICE_INCREASE
8. When increasing price, stay slightly below the cheapest relevant competitor instead of matching or exceeding them
9. When we are materially overpriced versus the market and can still preserve margin, prefer a measured PRICE_DROP instead of HOLD.
10. When stock is scarce and demand is rising, prefer a measured PRICE_INCREASE within the configured safety cap instead of HOLD.
11. When our current price is materially below the cheapest competitor and the increase remains within guardrails, prefer a measured PRICE_INCREASE instead of HOLD.
12. For realistic repricing, prefer small measured drops when we are only about 3% to 5% overpriced instead of matching a competitor's full discount immediately.

When you finish, return strict JSON with:
{
  "decision_type": "PRICE_DROP" | "PRICE_HOLD" | "PRICE_INCREASE" | "REORDER_ALERT",
  "reasoning": "concise business explanation",
  "confidence_score": 0.0 to 1.0,
  "proposed_price": number or null,
  "alert_message": "optional text"
}

Use tools whenever needed before deciding. Never expose hidden chain-of-thought. Give only concise reasoning summaries.
""".strip()


@dataclass(slots=True)
class AgentExecutionResult:
    """Normalized result returned after one event is processed by the pricing agent."""

    decision_type: AgentDecisionType
    reasoning: str
    confidence_score: float
    tools_used: list[str]
    execution_status: ExecutionStatus
    proposed_price: Decimal | None = None
    update_result: dict[str, Any] | None = None
    alert_payload: dict[str, Any] | None = None
    source_event_id: str | None = None
    audit_reasoning: str | None = None

    def to_kafka_payload(self, product_id: int, *, request_id: str | None = None) -> dict[str, Any]:
        """Convert the decision result into the event published to Kafka."""
        payload: dict[str, Any] = {
            "event_id": str(uuid4()),
            "product_id": product_id,
            "decision_type": self.decision_type.value,
            "reasoning": self.audit_reasoning or self.reasoning,
            "confidence_score": self.confidence_score,
            "tools_used": self.tools_used,
            "execution_status": self.execution_status.value,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "source_event_id": self.source_event_id,
        }
        if request_id:
            payload["request_id"] = request_id
        if self.proposed_price is not None:
            payload["proposed_price"] = float(self.proposed_price)
        if self.update_result is not None:
            payload["update_result"] = self.update_result
        return payload


class PricingDecisionAgent:
    """Run the GPT tool-calling loop, execute safe actions, and log decisions."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def process_event(self, event: dict[str, Any]) -> AgentExecutionResult:
        """Process one event end to end and return the final decision payload."""
        product_id = int(event["product_id"])
        source_event_id = str(event.get("event_id")) if event.get("event_id") else None
        request_id = str(event.get("request_id") or source_event_id or uuid4())

        if self._client is None:
            result = self._fallback_hold(
                source_event_id=source_event_id,
                reason="OpenAI API key is not configured. Falling back to HOLD.",
                product_id=product_id,
                source_event_data=event,
            )
            await self._log_decision(product_id, result)
            return result

        if not await self._is_runtime_active():
            result = self._fallback_hold(
                source_event_id=source_event_id,
                reason="Runtime session inactive. Open the dashboard to activate AI for 8 minutes.",
                product_id=product_id,
                source_event_data=event,
            )
            await self._log_decision(product_id, result)
            return result

        try:
            decision, tools_used = await self._run_agent_loop(event)
            result = await self._execute_decision(product_id, source_event_id, event, decision, tools_used)
        except Exception as exc:
            logger.exception("Pricing agent failed for product_id=%s", product_id)
            result = self._fallback_hold(
                source_event_id=source_event_id,
                reason=f"Agent execution failed: {exc}",
                product_id=product_id,
                source_event_data=event,
            )

        await self._log_decision(product_id, result)
        return result

    async def _is_runtime_active(self) -> bool:
        """Return True when at least one non-expired runtime session exists."""
        now = datetime.now(UTC)
        try:
            async with AsyncSessionLocal() as session:
                active_id = (
                    await session.execute(
                        select(RuntimeAccessSession.id)
                        .where(RuntimeAccessSession.expires_at > now)
                        .limit(1)
                    )
                ).scalar_one_or_none()
            return active_id is not None
        except Exception:
            logger.warning("Runtime session check failed; defaulting to inactive.")
            return False

    async def _run_agent_loop(self, event: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Run a multi-turn tool-calling loop until the model returns a final decision JSON object."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_event_prompt(event)},
        ]
        tools_used: list[str] = []

        for round_number in range(1, settings.openai_max_tool_rounds + 1):
            response = await self._create_completion_with_retry(messages)
            message = response.choices[0].message

            if message.tool_calls:
                tool_names = [tool_call.function.name for tool_call in message.tool_calls]
                tools_used.extend(tool_names)
                logger.info("Agent round %s requested tools: %s", round_number, ", ".join(tool_names))

                messages.append(self._assistant_message_payload(message))
                for tool_call in message.tool_calls:
                    tool_result = await self._execute_tool_call(tool_call)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result, default=self._json_default),
                        }
                    )
                continue

            content = (message.content or "").strip()
            logger.info("Agent final response received for product_id=%s", event.get("product_id"))
            return self._parse_final_decision(content), tools_used

        raise RuntimeError("Agent exceeded the maximum number of tool-calling rounds.")

    async def _create_completion_with_retry(self, messages: list[dict[str, Any]]):
        """Call OpenAI with retry logic for transient failures."""
        last_error: Exception | None = None
        for attempt in range(1, settings.openai_retry_attempts + 1):
            try:
                return await self._client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    tools=OPENAI_TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.2,
                )
            except (APIConnectionError, APITimeoutError, RateLimitError, APIError) as exc:
                last_error = exc
                if attempt == settings.openai_retry_attempts:
                    break
                delay = settings.openai_retry_base_delay_seconds * attempt
                logger.warning(
                    "OpenAI call failed on attempt %s/%s: %s. Retrying in %.1fs",
                    attempt,
                    settings.openai_retry_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError(f"OpenAI API request failed after retries: {last_error}")

    async def _execute_tool_call(self, tool_call: Any) -> dict[str, Any]:
        """Execute one model-requested tool and return a JSON-serializable result."""
        tool_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError as exc:
            logger.warning("Agent supplied invalid tool arguments for %s: %s", tool_name, exc)
            return {"error": f"Invalid JSON arguments for tool {tool_name}: {exc}"}

        tool = OPENAI_TOOL_FUNCTIONS.get(tool_name)
        if tool is None:
            logger.warning("Agent requested unknown tool: %s", tool_name)
            return {"error": f"Unknown tool: {tool_name}"}

        logger.info("Executing tool %s with args=%s", tool_name, arguments)

        try:
            result = await tool(**arguments)
            logger.info("Tool %s completed successfully", tool_name)
            return {"ok": True, "tool_name": tool_name, "data": result}
        except Exception as exc:
            logger.exception("Tool %s failed", tool_name)
            return {"ok": False, "tool_name": tool_name, "error": str(exc)}

    async def _execute_decision(
        self,
        product_id: int,
        source_event_id: str | None,
        source_event: dict[str, Any],
        decision: dict[str, Any],
        runtime_tools_used: list[str],
    ) -> AgentExecutionResult:
        """Apply the model's final decision and normalize the stored/published result."""
        decision_type = self._parse_decision_type(decision.get("decision_type"))
        reasoning = str(decision.get("reasoning") or "No reasoning provided.")
        confidence_score = self._normalize_confidence(decision.get("confidence_score"))
        tools_used = runtime_tools_used or self._normalize_tools_used(decision)
        proposed_price = self._parse_optional_price(decision.get("proposed_price"))
        product_details = await get_product_details(product_id)
        market_position = await get_market_position(product_id)
        demand_trend = await get_demand_trend(product_id)
        override = self._maybe_override_hold(
            decision_type=decision_type,
            current_reasoning=reasoning,
            current_confidence=confidence_score,
            current_proposed_price=proposed_price,
            source_event=source_event,
            product_details=product_details,
            market_position=market_position,
            demand_trend=demand_trend,
        )
        if override is not None:
            decision_type, proposed_price, reasoning, confidence_score = override
        normalized = self._maybe_normalize_proposed_price(
            decision_type=decision_type,
            proposed_price=proposed_price,
            current_price=Decimal(str(product_details["our_price"])),
            minimum_allowed_price=self._minimum_allowed_price(
                Decimal(str(product_details["cost_price"])),
                Decimal(str(product_details["min_margin_percent"])),
            ),
            market_position=market_position,
        )
        if normalized is not None:
            proposed_price, normalization_reason = normalized
            reasoning = f"{reasoning} {normalization_reason}"
        current_price = Decimal(str(product_details["our_price"]))
        product_name = str(product_details["name"])

        if decision_type in {AgentDecisionType.PRICE_DROP, AgentDecisionType.PRICE_INCREASE}:
            if proposed_price is None:
                return self._fallback_hold(
                    source_event_id=source_event_id,
                    reason="Agent requested a price change but did not return a valid proposed_price.",
                    tools_used=tools_used,
                    product_id=product_id,
                    product_name=product_name,
                    current_price=current_price,
                    source_event_data=source_event,
                )

            direction_failure = self._validate_event_direction_consistency(
                decision_type=decision_type,
                source_event=source_event,
                current_price=current_price,
                market_position=market_position,
                demand_trend=demand_trend,
            )
            if direction_failure is not None:
                return self._fallback_hold(
                    source_event_id=source_event_id,
                    reason=direction_failure,
                    tools_used=tools_used,
                    product_id=product_id,
                    product_name=product_name,
                    current_price=current_price,
                    source_event_data=source_event,
                )

            guardrail_failure = self._validate_price_change_guardrails(
                decision_type=decision_type,
                current_price=current_price,
                proposed_price=proposed_price,
                market_position=market_position,
            )
            if guardrail_failure is not None:
                return self._fallback_hold(
                    source_event_id=source_event_id,
                    reason=guardrail_failure,
                    tools_used=tools_used,
                    product_id=product_id,
                    product_name=product_name,
                    current_price=current_price,
                    source_event_data=source_event,
                )

            audit_reason = self._build_audit_reason(
                event_decision_reason=reasoning,
                event_product_name=product_name,
                event_current_price=current_price,
                event_new_price=proposed_price,
                source_event_id=source_event_id,
                source_event_data=source_event,
            )

            update_result = await update_product_price(
                product_id=product_id,
                new_price=proposed_price,
                reason=audit_reason,
            )

            if not update_result.get("success"):
                final_reasoning = f"{reasoning} Update rejected: {update_result.get('message')}"
                return AgentExecutionResult(
                    decision_type=AgentDecisionType.PRICE_HOLD,
                    reasoning=final_reasoning,
                    confidence_score=confidence_score,
                    tools_used=tools_used + ["update_product_price"],
                    execution_status=ExecutionStatus.REJECTED,
                    proposed_price=proposed_price,
                    update_result=update_result,
                    alert_payload=self._build_human_intervention_alert(
                        product_id=product_id,
                        reason=final_reasoning,
                        source_event_id=source_event_id,
                    ),
                    source_event_id=source_event_id,
                    audit_reasoning=self._build_decision_audit_reasoning(
                        decision_type=AgentDecisionType.PRICE_HOLD,
                        product_name=product_name,
                        current_price=current_price,
                        proposed_price=None,
                        source_event_id=source_event_id,
                        source_event_data=source_event,
                        model_reasoning=final_reasoning,
                    ),
                )

            return AgentExecutionResult(
                decision_type=decision_type,
                reasoning=reasoning,
                confidence_score=confidence_score,
                tools_used=tools_used + ["update_product_price"],
                execution_status=ExecutionStatus.EXECUTED,
                proposed_price=proposed_price,
                update_result=update_result,
                source_event_id=source_event_id,
                audit_reasoning=self._build_decision_audit_reasoning(
                    decision_type=decision_type,
                    product_name=product_name,
                    current_price=current_price,
                    proposed_price=proposed_price,
                    source_event_id=source_event_id,
                    source_event_data=source_event,
                    model_reasoning=reasoning,
                ),
            )

        if decision_type is AgentDecisionType.REORDER_ALERT:
            alert_payload = {
                "event_id": str(uuid4()),
                "request_id": request_id,
                "product_id": product_id,
                "alert_type": "REORDER_ALERT",
                "reason": str(decision.get("alert_message") or reasoning),
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
            return AgentExecutionResult(
                decision_type=decision_type,
                reasoning=reasoning,
                confidence_score=confidence_score,
                tools_used=tools_used,
                execution_status=ExecutionStatus.EXECUTED,
                alert_payload=alert_payload,
                source_event_id=source_event_id,
                audit_reasoning=self._build_decision_audit_reasoning(
                    decision_type=decision_type,
                    product_name=product_name,
                    current_price=current_price,
                    proposed_price=None,
                    source_event_id=source_event_id,
                    source_event_data=source_event,
                    model_reasoning=reasoning,
                ),
            )

        return AgentExecutionResult(
            decision_type=AgentDecisionType.PRICE_HOLD,
            reasoning=reasoning,
            confidence_score=confidence_score,
            tools_used=tools_used,
            execution_status=ExecutionStatus.EXECUTED,
            source_event_id=source_event_id,
            audit_reasoning=self._build_decision_audit_reasoning(
                decision_type=AgentDecisionType.PRICE_HOLD,
                product_name=product_name,
                current_price=current_price,
                proposed_price=None,
                source_event_id=source_event_id,
                source_event_data=source_event,
                model_reasoning=reasoning,
            ),
        )

    async def _log_decision(self, product_id: int, result: AgentExecutionResult) -> None:
        """Persist the decision summary in the agent_decisions table."""
        async with AsyncSessionLocal() as session:
            session.add(
                AgentDecision(
                    product_id=product_id,
                    decision_type=result.decision_type,
                    reasoning=result.audit_reasoning or result.reasoning,
                    confidence_score=result.confidence_score,
                    tools_used=result.tools_used,
                    execution_status=result.execution_status,
                )
            )
            await session.commit()

    def _fallback_hold(
        self,
        source_event_id: str | None,
        reason: str,
        tools_used: list[str] | None = None,
        product_id: int | None = None,
        product_name: str | None = None,
        current_price: Decimal | None = None,
        source_event_data: dict[str, Any] | None = None,
    ) -> AgentExecutionResult:
        """Return a safe HOLD decision used when the smart path cannot complete."""
        logger.warning("Falling back to HOLD: %s", reason)
        return AgentExecutionResult(
            decision_type=AgentDecisionType.PRICE_HOLD,
            reasoning=reason,
            confidence_score=0.0,
            tools_used=tools_used or [],
            execution_status=ExecutionStatus.REJECTED,
            alert_payload=self._build_human_intervention_alert(
                product_id=product_id,
                reason=reason,
                source_event_id=source_event_id,
            ),
            source_event_id=source_event_id,
            audit_reasoning=(
                self._build_decision_audit_reasoning(
                    decision_type=AgentDecisionType.PRICE_HOLD,
                    product_name=product_name,
                    current_price=current_price,
                    proposed_price=None,
                    source_event_id=source_event_id,
                    source_event_data=source_event_data,
                    model_reasoning=reason,
                )
                if product_name is not None and current_price is not None and source_event_data is not None
                else reason
            ),
        )

    def _build_human_intervention_alert(
        self,
        *,
        product_id: int | None,
        reason: str,
        source_event_id: str | None,
    ) -> dict[str, Any] | None:
        """Build an alerts-topic payload when AI decision execution is rejected and needs review."""
        if product_id is None:
            return None
        return {
            "event_id": str(uuid4()),
            "product_id": product_id,
            "alert_type": "HUMAN_INTERVENTION_REQUIRED",
            "reason": reason,
            "source_event_id": source_event_id,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    def _build_event_prompt(self, event: dict[str, Any]) -> str:
        """Build the user prompt containing the market event and decision instructions."""
        return (
            "Analyze this competitor-price event and decide the best pricing action.\n"
            "Use tools before deciding if more context is needed.\n"
            "Prefer a safe price change over HOLD when the market evidence is strong.\n"
            "Return only the final JSON object once you are done.\n\n"
            f"Event:\n{json.dumps(event, default=self._json_default, indent=2)}"
        )

    def _maybe_override_hold(
        self,
        *,
        decision_type: AgentDecisionType,
        current_reasoning: str,
        current_confidence: float,
        current_proposed_price: Decimal | None,
        source_event: dict[str, Any],
        product_details: dict[str, Any],
        market_position: dict[str, Any],
        demand_trend: dict[str, Any],
    ) -> tuple[AgentDecisionType, Decimal, str, float] | None:
        """Replace overly conservative HOLDs with a safe deterministic price move when signals are strong."""
        if decision_type is not AgentDecisionType.PRICE_HOLD or current_proposed_price is not None:
            return None

        current_price = Decimal(str(product_details["our_price"]))
        cost_price = Decimal(str(product_details["cost_price"]))
        min_margin_percent = Decimal(str(product_details["min_margin_percent"]))
        stock = int(product_details["stock"])
        cheapest_competitor = market_position.get("cheapest_competitor_price")
        gap_percent = market_position.get("price_gap_to_cheapest_percent")
        trend = str(demand_trend.get("trend") or "stable").lower()

        if cheapest_competitor is not None and gap_percent is not None:
            cheapest_competitor_price = Decimal(str(cheapest_competitor))
            market_gap_percent = Decimal(str(gap_percent))

            min_allowed_price = self._minimum_allowed_price(cost_price, min_margin_percent)
            if (
                not self._event_represents_competitor_price_increase(source_event)
                and self._market_price_is_not_improving(source_event, cheapest_competitor_price)
                and market_gap_percent <= Decimal(str(-settings.strategic_drop_min_gap_percent))
                and trend != "rising"
                and current_price > min_allowed_price
            ):
                target_drop_percent = min(
                    Decimal(str(settings.max_price_drop_percent_per_action)),
                    max(Decimal("1.5"), abs(market_gap_percent) * Decimal("0.65")),
                )
                candidate = current_price * (Decimal("1") - (target_drop_percent / Decimal("100")))
                candidate = max(candidate.quantize(Decimal("0.01")), min_allowed_price)
                if candidate < current_price:
                    reasoning = (
                        f"{current_reasoning} Deterministic override applied: our price is materially above the "
                        f"cheapest competitor, so applying a measured drop to {candidate} instead of matching the "
                        f"lowest competitor immediately."
                    )
                    return (AgentDecisionType.PRICE_DROP, candidate, reasoning, max(current_confidence, 0.82))

            if (
                market_gap_percent >= Decimal(str(settings.strategic_increase_min_gap_percent))
                and (stock <= settings.low_stock_threshold or trend in {"stable", "rising"})
            ):
                safe_ceiling = cheapest_competitor_price * (
                    Decimal("1") - (Decimal(str(settings.competitor_price_buffer_percent)) / Decimal("100"))
                )
                safe_ceiling = safe_ceiling.quantize(Decimal("0.01"))
                target_increase_percent = min(
                    Decimal(str(settings.max_price_increase_percent_per_action)),
                    max(Decimal("3.0"), market_gap_percent * Decimal("0.65")),
                )
                candidate = current_price * (Decimal("1") + (target_increase_percent / Decimal("100")))
                candidate = min(candidate.quantize(Decimal("0.01")), safe_ceiling)
                if candidate > current_price:
                    reasoning = (
                        f"{current_reasoning} Deterministic override applied: our price is meaningfully below the "
                        f"cheapest competitor and the market supports a safe increase to {candidate}."
                    )
                    return (AgentDecisionType.PRICE_INCREASE, candidate, reasoning, max(current_confidence, 0.84))

            if self._should_rebalance_hold(source_event):
                if market_gap_percent <= Decimal("-0.5") and current_price > min_allowed_price:
                    target_drop_percent = min(
                        Decimal(str(settings.max_price_drop_percent_per_action)),
                        max(Decimal("1.0"), abs(market_gap_percent) * Decimal("0.45")),
                    )
                    candidate = current_price * (Decimal("1") - (target_drop_percent / Decimal("100")))
                    candidate = max(candidate.quantize(Decimal("0.01")), min_allowed_price)
                    if candidate < current_price:
                        reasoning = (
                            f"{current_reasoning} Policy rebalance applied to reduce HOLD dominance: "
                            f"safe strategic drop to {candidate}."
                        )
                        return (AgentDecisionType.PRICE_DROP, candidate, reasoning, max(current_confidence, 0.8))

                if market_gap_percent >= Decimal("0.5"):
                    safe_ceiling = cheapest_competitor_price * (
                        Decimal("1") - (Decimal(str(settings.competitor_price_buffer_percent)) / Decimal("100"))
                    )
                    safe_ceiling = safe_ceiling.quantize(Decimal("0.01"))
                    target_increase_percent = min(
                        Decimal(str(settings.max_price_increase_percent_per_action)),
                        max(Decimal("1.0"), market_gap_percent * Decimal("0.45")),
                    )
                    candidate = current_price * (Decimal("1") + (target_increase_percent / Decimal("100")))
                    candidate = min(candidate.quantize(Decimal("0.01")), safe_ceiling)
                    if candidate > current_price:
                        reasoning = (
                            f"{current_reasoning} Policy rebalance applied to reduce HOLD dominance: "
                            f"safe strategic increase to {candidate}."
                        )
                        return (AgentDecisionType.PRICE_INCREASE, candidate, reasoning, max(current_confidence, 0.8))

        return None

    def _should_rebalance_hold(self, source_event: dict[str, Any]) -> bool:
        """Deterministically rebalance about 75% of HOLD outputs into safe actions."""
        key = str(
            source_event.get("event_id")
            or source_event.get("request_id")
            or f"{source_event.get('product_id', 'unknown')}-{source_event.get('timestamp', 'unknown')}"
        )
        bucket = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < 75

    def _validate_event_direction_consistency(
        self,
        *,
        decision_type: AgentDecisionType,
        source_event: dict[str, Any],
        current_price: Decimal,
        market_position: dict[str, Any],
        demand_trend: dict[str, Any],
    ) -> str | None:
        """Reject drops triggered by an upward competitor move unless evidence is unusually strong."""
        if decision_type is not AgentDecisionType.PRICE_DROP:
            return None
        if not self._event_represents_competitor_price_increase(source_event):
            return None

        trend = str(demand_trend.get("trend") or "stable").lower()
        if trend == "falling":
            return None

        gap_percent = market_position.get("price_gap_to_cheapest_percent")
        if gap_percent is not None and Decimal(str(gap_percent)) <= Decimal("-1.0"):
            return None

        cheapest_competitor = market_position.get("cheapest_competitor_price")
        if cheapest_competitor is None:
            return "Triggering competitor raised price and there is no market data strong enough to justify a drop."

        cheapest_competitor_price = Decimal(str(cheapest_competitor))
        if cheapest_competitor_price >= current_price:
            return "Triggering competitor raised price and we are no longer above the cheapest competitor, so defaulting to HOLD."

        return (
            "Triggering competitor raised price. Defaulting to HOLD instead of dropping while demand is not falling."
        )

    def _event_represents_competitor_price_increase(self, source_event: dict[str, Any]) -> bool:
        """Return True when the triggering competitor event moved upward."""
        old_price = self._parse_optional_price(source_event.get("old_price"))
        new_price = self._parse_optional_price(source_event.get("new_price"))
        return old_price is not None and new_price is not None and new_price > old_price

    def _market_price_is_not_improving(
        self,
        source_event: dict[str, Any],
        cheapest_competitor_price: Decimal,
    ) -> bool:
        """Return True when the triggering event did not make the market more expensive."""
        new_price = self._parse_optional_price(source_event.get("new_price"))
        if new_price is None:
            return True
        return cheapest_competitor_price <= new_price

    def _minimum_allowed_price(self, cost_price: Decimal, min_margin_percent: Decimal) -> Decimal:
        """Return the minimum price that still satisfies the configured margin floor."""
        denominator = Decimal("1") - (min_margin_percent / Decimal("100"))
        if denominator <= 0:
            return cost_price
        return (cost_price / denominator).quantize(Decimal("0.01"))

    def _maybe_normalize_proposed_price(
        self,
        *,
        decision_type: AgentDecisionType,
        proposed_price: Decimal | None,
        current_price: Decimal,
        minimum_allowed_price: Decimal,
        market_position: dict[str, Any],
    ) -> tuple[Decimal, str] | None:
        """Clamp oversized model proposals into the configured safe operating window."""
        if proposed_price is None:
            return None

        if decision_type is AgentDecisionType.PRICE_DROP:
            max_drop_price = current_price * (
                Decimal("1") - (Decimal(str(settings.max_price_drop_percent_per_action)) / Decimal("100"))
            )
            max_drop_price = max_drop_price.quantize(Decimal("0.01"))
            floored_price = max(proposed_price, max_drop_price, minimum_allowed_price)

            if floored_price >= current_price or floored_price == proposed_price:
                return None

            return (
                floored_price,
                (
                    f"Proposal normalized to {floored_price} so the drop stays within the "
                    f"{settings.max_price_drop_percent_per_action}% cap and margin floor."
                ),
            )

        if decision_type is not AgentDecisionType.PRICE_INCREASE:
            return None

        max_increase_price = current_price * (
            Decimal("1") + (Decimal(str(settings.max_price_increase_percent_per_action)) / Decimal("100"))
        )
        max_increase_price = max_increase_price.quantize(Decimal("0.01"))

        cheapest_competitor_price = market_position.get("cheapest_competitor_price")
        safe_ceiling = None
        if cheapest_competitor_price is not None:
            safe_ceiling = Decimal(str(cheapest_competitor_price)) * (
                Decimal("1") - (Decimal(str(settings.competitor_price_buffer_percent)) / Decimal("100"))
            )
            safe_ceiling = safe_ceiling.quantize(Decimal("0.01"))

        capped_price = proposed_price
        if proposed_price > max_increase_price:
            capped_price = max_increase_price
        if safe_ceiling is not None and capped_price > safe_ceiling:
            capped_price = safe_ceiling

        if capped_price <= current_price or capped_price == proposed_price:
            return None

        return (
            capped_price,
            (
                f"Proposal normalized to {capped_price} so the increase stays within the "
                f"{settings.max_price_increase_percent_per_action}% cap and competitor safety ceiling."
            ),
        )

    def _validate_price_change_guardrails(
        self,
        decision_type: AgentDecisionType,
        current_price: Decimal,
        proposed_price: Decimal,
        market_position: dict[str, Any],
    ) -> str | None:
        """Reject unsafe repricing actions before they hit the database."""
        if proposed_price <= 0:
            return "Proposed price must be positive."

        if decision_type is AgentDecisionType.PRICE_DROP:
            drop_percent = ((current_price - proposed_price) / current_price) * Decimal("100")
            if drop_percent > Decimal(str(settings.max_price_drop_percent_per_action)):
                return (
                    f"Proposed drop of {round(float(drop_percent), 2)}% exceeds the "
                    f"{settings.max_price_drop_percent_per_action}% per-action safety cap."
                )

            gap_percent = market_position.get("price_gap_to_cheapest_percent")
            if gap_percent is None:
                return "Cannot justify a strategic price drop without competitor market position data."

            if float(gap_percent) > -settings.strategic_drop_min_gap_percent:
                return (
                    f"Competitive overpricing gap of {gap_percent}% is below the "
                    f"{settings.strategic_drop_min_gap_percent}% threshold for a strategic price drop."
                )
            return None

        if decision_type is not AgentDecisionType.PRICE_INCREASE:
            return None

        increase_percent = ((proposed_price - current_price) / current_price) * Decimal("100")
        if increase_percent > Decimal(str(settings.max_price_increase_percent_per_action)):
            return (
                f"Proposed increase of {round(float(increase_percent), 2)}% exceeds the "
                f"{settings.max_price_increase_percent_per_action}% per-action safety cap."
            )

        cheapest_competitor_price = market_position.get("cheapest_competitor_price")
        gap_percent = market_position.get("price_gap_to_cheapest_percent")
        if cheapest_competitor_price is None or gap_percent is None:
            return "Cannot justify a strategic price increase without competitor market position data."

        if float(gap_percent) < settings.strategic_increase_min_gap_percent:
            return (
                f"Competitive gap of {gap_percent}% is below the "
                f"{settings.strategic_increase_min_gap_percent}% threshold for safe upward repricing."
            )

        safe_ceiling = Decimal(str(cheapest_competitor_price)) * (
            Decimal("1") - (Decimal(str(settings.competitor_price_buffer_percent)) / Decimal("100"))
        )
        safe_ceiling = safe_ceiling.quantize(Decimal("0.01"))
        if proposed_price > safe_ceiling:
            return (
                f"Proposed price {proposed_price} exceeds the safe competitor ceiling {safe_ceiling}, "
                f"which keeps us {settings.competitor_price_buffer_percent}% below the cheapest competitor."
            )

        return None

    def _build_audit_reason(
        self,
        event_decision_reason: str,
        event_product_name: str,
        event_current_price: Decimal,
        event_new_price: Decimal,
        source_event_id: str | None,
        source_event_data: dict[str, Any],
    ) -> str:
        """Build a business-readable audit message for price_history."""
        competitor_name = source_event_data.get("competitor_name") or "unknown competitor"
        competitor_old_price = source_event_data.get("old_price")
        competitor_new_price = source_event_data.get("new_price")
        change_percent = source_event_data.get("change_percent")

        competitor_context = (
            f"Competitor {competitor_name} moved from {competitor_old_price} to {competitor_new_price}"
            if competitor_old_price is not None and competitor_new_price is not None
            else f"Competitor {competitor_name} triggered the pricing review"
        )
        if change_percent is not None:
            competitor_context += f" ({change_percent}% change)"

        return (
            f"Product '{event_product_name}': {competitor_context}. "
            f"Our current price was {event_current_price}. "
            f"Our new price is {event_new_price}. "
            f"Agent reasoning: {event_decision_reason}. "
            f"Source event id: {source_event_id or 'n/a'}."
        )

    def _build_decision_audit_reasoning(
        self,
        decision_type: AgentDecisionType,
        product_name: str | None,
        current_price: Decimal | None,
        proposed_price: Decimal | None,
        source_event_id: str | None,
        source_event_data: dict[str, Any] | None,
        model_reasoning: str,
    ) -> str:
        """Build a readable audit summary for agent_decisions."""
        if product_name is None or current_price is None or source_event_data is None:
            return model_reasoning

        competitor_name = source_event_data.get("competitor_name") or "unknown competitor"
        competitor_old_price = source_event_data.get("old_price")
        competitor_new_price = source_event_data.get("new_price")
        change_percent = source_event_data.get("change_percent")

        competitor_context = (
            f"Competitor {competitor_name} moved from {competitor_old_price} to {competitor_new_price}"
            if competitor_old_price is not None and competitor_new_price is not None
            else f"Competitor {competitor_name} triggered the pricing review"
        )
        if change_percent is not None:
            competitor_context += f" ({change_percent}% change)"

        price_action = (
            f"Our current price is {current_price}. Proposed new price is {proposed_price}."
            if proposed_price is not None
            else f"Our current price remains {current_price}."
        )

        return (
            f"Decision {decision_type.value} for product '{product_name}'. "
            f"{competitor_context}. "
            f"{price_action} "
            f"Agent reasoning: {model_reasoning}. "
            f"Source event id: {source_event_id or 'n/a'}."
        )

    def _assistant_message_payload(self, message: Any) -> dict[str, Any]:
        """Convert the SDK assistant message into a message payload suitable for the next round."""
        payload: dict[str, Any] = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in message.tool_calls
            ],
        }
        if message.content:
            payload["content"] = message.content
        return payload

    def _parse_final_decision(self, content: str) -> dict[str, Any]:
        """Parse the final JSON decision emitted by the model."""
        if not content:
            raise RuntimeError("Model returned an empty final response.")

        candidate = content.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            candidate = candidate.replace("json", "", 1).strip()

        try:
            decision = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model returned invalid JSON: {exc}: {content}") from exc

        if not isinstance(decision, dict):
            raise RuntimeError("Model returned a non-object final decision.")
        return decision

    def _parse_decision_type(self, value: Any) -> AgentDecisionType:
        """Normalize the model decision type and default to HOLD when it is invalid."""
        try:
            return AgentDecisionType(str(value).upper())
        except ValueError:
            return AgentDecisionType.PRICE_HOLD

    def _parse_optional_price(self, value: Any) -> Decimal | None:
        """Parse an optional price from the model output."""
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except Exception:
            return None

    def _normalize_confidence(self, value: Any) -> float:
        """Normalize confidence into the range [0.0, 1.0]."""
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, round(confidence, 4)))

    def _normalize_tools_used(self, decision: dict[str, Any]) -> list[str]:
        """Extract the tool usage list if the model provides one; otherwise derive it later from runtime logs."""
        tools_used = decision.get("tools_used")
        if not isinstance(tools_used, list):
            return []
        return [str(tool_name) for tool_name in tools_used]

    def _json_default(self, value: Any) -> str | float:
        """Serialize Decimal and datetime values into JSON-safe types."""
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

# PriceWise Interview Prep (Q&A)

Use this as your speaking script. Keep answers practical and tied to your implementation.

## 1) High-Level Understanding (Most Important)

### Q: Walk me through the system end to end. A price change happens - what flows where?
**Answer:**
1. Simulators (demand/competitor/inventory) publish market signals to Kafka.
2. Pricing agent consumes events, loads current product context from Postgres, runs rule checks, then (if needed) asks the LLM for recommendation.
3. Guardrails validate the recommendation (margin floor, stock/risk constraints, policy checks).
4. Agent publishes decision/result events to Kafka and writes decision history to Postgres.
5. Dashboard API consumes Kafka events + reads DB state, exposes REST + WebSocket.
6. Frontend dashboard gets initial data via REST and live updates via WebSocket.

### Q: Why this architecture, not a monolith + cron?
**Answer:**
- Event-driven design gives near real-time pricing reaction instead of batch delays.
- Kafka decouples producers and consumers so services can scale independently.
- Replayable log allows reprocessing and debugging history.
- Isolated services reduce blast radius and make experimentation safer.

### Q: Draw architecture on whiteboard.
**Answer (boxes):**
`Simulators -> Kafka -> Pricing Agent -> Kafka + Postgres -> Dashboard API -> WebSocket/REST -> Vite Frontend`

---

## 2) Kafka Questions

### Q: Why Kafka vs Redis Pub/Sub or RabbitMQ?
**Answer:**
- Kafka is durable + replayable (log retention + offsets).
- Better fit for event streams, analytics, and rebuilding state from history.
- Consumer groups give horizontal scaling and controlled processing.
- Redis Pub/Sub is transient; RabbitMQ is queue-oriented but not log-replay first.

### Q: What topics and why?
**Answer:**
- `price-changes`: emitted when price updates happen.
- `price-decisions`: agent decisions and decision metadata.
- `alerts`: operational/business alerts (including human-intervention-required cases).

### Q: Consumer crashes mid-processing - lose message?
**Answer:**
- We use Kafka offsets with consumer groups. If crash happens before commit, message is reprocessed.
- This gives at-least-once delivery behavior.

### Q: How do you handle duplicates?
**Answer:**
- Idempotent handling using stable identifiers (event/decision context).
- DB writes and decision tracking are designed so reprocessing does not create invalid business state.

---

## 3) AI/LLM Agent Questions

### Q: Why hybrid approach, not only OpenAI?
**Answer:**
- Deterministic rules are faster/cheaper and handle clear no-go cases.
- LLM is used only for context-heavy judgment where rules are not enough.
- Hybrid improves reliability and cost control.

### Q: What does prefilter check?
**Answer:**
- Hard business constraints: margin floor, stock safety, invalid/unsafe action patterns, policy boundaries.
- If constraints fail, decision is rejected/held before execution.

### Q: Prompt/tool-calling design?
**Answer:**
- Structured prompt with product context, constraints, and allowed action space.
- Model output is constrained to a decision schema (action, reason, confidence, etc.).
- Post-validation still applies; LLM is advisory, not autonomous executor.

### Q: What if LLM gives bad recommendation?
**Answer:**
- Guardrails block unsafe output.
- Fallback action is HOLD/no-op when confidence or constraints fail.
- Rejected actions are logged and surfaced as alert signals.

### Q: How did you test correctness?
**Answer:**
- Scenario-based tests with simulator inputs.
- Validation of accepted vs rejected decision paths.
- End-to-end checks through Kafka -> DB -> dashboard.
- Manual audit using decision history and reason fields.

---

## 4) Database Questions

### Q: Schema overview?
**Answer:**
Core relational entities:
- `products` (catalog + pricing state)
- `competitor_prices` (external market references)
- `price_history` (time-series of price changes)
- `agent_decisions` (decision audit trail: proposed/accepted/rejected/reason)

### Q: How do you store audit history?
**Answer:**
- Every decision and price update is persisted with timestamps and rationale.
- This supports explainability, rollback analysis, and post-incident review.

### Q: Why PostgreSQL over MongoDB?
**Answer:**
- Pricing domain is relational and consistency-sensitive.
- Strong schema + SQL querying is useful for analytics, joins, and audit reports.

---

## 5) FastAPI / Python Questions

### Q: Why FastAPI?
**Answer:**
- Async-native, high performance, type hints + validation, clean API docs.
- Great fit for I/O-heavy workloads (DB, Kafka, WebSocket, external API calls).

### Q: Why async matters here?
**Answer:**
- Avoids thread blocking during network/database waits.
- Improves concurrency for live dashboard + background event processing.

### Q: Error handling approach?
**Answer:**
- Explicit HTTP exceptions, structured JSON errors, startup/readiness checks, container health checks.
- Fail-safe behavior in agent path (fallback HOLD).

---

## 6) Frontend / WebSocket Questions

### Q: How does dashboard get real-time updates?
**Answer:**
- Initial page data from REST.
- Continuous event updates from dashboard WebSocket (`/ws/live-feed`).
- UI state reconciles stream events with existing view data.

### Q: What if WebSocket drops?
**Answer:**
- Frontend detects disconnect, shows status, retries connection.
- REST endpoints still provide baseline data.

### Q: What are you visualizing?
**Answer:**
- Decision activity, top movers, alerts, margin indicators, runtime session status.
- Goal: operational visibility + quick intervention.

---

## 7) Deployment Questions

### Q: How did you containerize?
**Answer:**
- Multi-service Docker Compose stack: Postgres, Kafka/Zookeeper, simulators, pricing agent, dashboard API, kafka-ui, reverse proxy.
- Each service has isolated image and runtime env.

### Q: Service discovery in Compose?
**Answer:**
- Containers communicate via Compose network using service names as DNS hosts.
- Example: dashboard API reaches Kafka by `kafka:9092`.

### Q: Why Azure VM instead of ECS/K8s?
**Answer:**
- Faster/cheaper for prototype and interview project timeline.
- Full control for debugging networking, TLS, and system-level setup.
- Easy migration path later to managed orchestrators.

---

## 8) Human Intervention Story (Good Differentiator)

Say this clearly:
- "I don’t let the model blindly execute changes. When decisions violate guardrails or are not confidently executable, they are marked for human intervention."
- "I added explicit human-intervention alerting for rejected paths so operators can review."

This shows ownership, safety mindset, and production thinking.

---

## 9) 45-Second Project Pitch

"PriceWise is an event-driven dynamic pricing platform. Simulators stream market signals into Kafka, a hybrid pricing agent applies deterministic guardrails and LLM reasoning, and only safe decisions are applied and audited in PostgreSQL. The dashboard API exposes REST and WebSocket for live operations, so users can monitor decisions, margins, and alerts in real time. I deployed it with Docker Compose on Azure VM and set up HTTPS with domain routing for production-like behavior."

---

## 10) Final Prep Checklist

- Practice event flow 5 times without notes.
- Be able to justify Kafka and hybrid AI design in 2 minutes.
- Memorize your 4 main DB tables and purpose.
- Be ready to explain one failure case and fallback behavior.
- Keep answers practical: "what I built, why, tradeoff."

# PriceWise
### Real-time AI pricing intelligence for competitive e-commerce operations

PriceWise is an event-driven pricing simulation platform for e-commerce teams. Competitor and demand simulators publish market events into Kafka, a guarded AI pricing agent evaluates those signals, and a React dashboard shows products, decisions, alerts, and margin impact in real time.

---

## Screenshots

![Dashboard](docs/dashboard.png)
![Products](docs/products.png)
![Decisions](docs/decisions.png)
![Alerts](docs/alerts.png)
![Margins](docs/margins.png)

---

## What It Does

- Simulates competitor price movement and demand changes against a shared product catalog.
- Streams events through Kafka to inventory and pricing services.
- Uses an OpenAI-powered pricing agent with tool calls, deterministic overrides, and hard guardrails.
- Exposes REST APIs plus WebSocket live feeds for a dashboard.
- Tracks pricing decisions, price history, low-stock pressure, and margin health.

---

## HLD (High Level Design)

### 1) Business Objective

Provide an operations-grade, real-time pricing intelligence surface for e-commerce teams by combining:

- Event-driven market simulation (competitor movement, demand/orders)
- Guarded automated pricing recommendations/execution
- A dashboard that surfaces product health, decisions, alerts, and margin impact

### 2) Scope

In scope:

- Product catalog CRUD + analytics APIs
- Kafka-based event stream (pricing signals, orders, alerts, decisions)
- Pricing agent with deterministic guardrails and optional OpenAI reasoning
- Inventory updates driven by order events
- WebSocket live feeds for operational UI

Out of scope (by design for this demo/simulator):

- Payment, fulfillment, and real ERP integrations
- User auth/SSO and RBAC (runtime activation is the primary gating mechanism here)
- Multi-tenant isolation

### 3) System Context (C4-L1)

Primary actors:

- E-commerce operator (uses the dashboard)
- Market simulators (produce competitor and demand events)
- Pricing automation (processes competitor signals into decisions/alerts)

### 4) Logical Architecture (C4-L2)

```mermaid
flowchart LR
    CS[Competitor Simulator] -->|price-changes| K[(Kafka)]
    DS[Demand Simulator] -->|orders| K

    K -->|orders| IS[Inventory Service]
    IS -->|inventory-updates| K
    IS -->|alerts: low stock| K

    K -->|price-changes| PA[Pricing Agent]
    PA -->|price-decisions| K
    PA -->|alerts: reorder| K

    PA -->|read/write| DB[(PostgreSQL)]
    IS -->|read/write| DB
    CS -->|read/write snapshots| DB
    DS -->|read/write snapshots| DB

    API["Dashboard API\nFastAPI + WebSocket bridge"] <-->|queries| DB
    API <-->|consume + stream events| K

    FE[React Dashboard] <-->|REST + WebSocket| API
```

**Kafka topics**
- `price-changes`
- `orders`
- `inventory-updates`
- `price-decisions`
- `alerts`

### 5) Deployment View

Local / demo deployment is Docker Compose:

- `postgres` (shared persistence)
- `kafka` + `zookeeper` (event bus)
- `kafka-ui` (ops visibility)
- `dashboard-api` (FastAPI + WebSockets + Kafka bridge)
- `pricing-agent` (Kafka consumer + rule engine + optional OpenAI tool-calling)
- `inventory-service` (Kafka consumer that applies order events to stock)
- `competitor-simulator` (publisher for competitor movement)
- `demand-simulator` (publisher for orders)
- `frontend` runs separately via Vite dev server

### 6) Key Non-Functional Requirements (NFRs)

- Safety: pricing actions are constrained by margin floors, significance thresholds, cooldowns, and per-action caps.
- Resilience: Kafka clients retry on startup; consumers tolerate transient failures; services emit heartbeats for healthchecks.
- Observability: JSON logs with propagated `request_id`; operational events also visible via Kafka UI and dashboard live feed.
- Performance: pricing agent uses a bounded in-memory queue + configurable concurrency for controlled throughput.

### 7) Security & Data Handling (Demo Posture)

- No end-user identity or authorization model is implemented beyond the runtime-session gate.
- Secrets are read via environment variables (e.g., `OPENAI_API_KEY`), and OpenAI calls are disabled when not configured.
- All inbound/outbound payloads are JSON; invalid Kafka payloads are safely dropped.

---

## LLD (Low Level Design)

### 1) Service Responsibilities

`services/dashboard-api` (FastAPI):

- Product CRUD and dashboard enrichment (competitor snapshots, margin %, 24h deltas)
- Analytics endpoints (summary + top movers)
- Runtime-session endpoints used to activate the simulation/agent pipeline for a limited window
- WebSocket endpoints and a background Kafka consumer that forwards events to WebSocket rooms

`services/pricing-agent` (async worker service):

- Consumes `price-changes`
- Applies a fast-path rule engine (ignore noise, prevent feedback loops, enforce cooldown, create direct alerts on stock=0)
- When eligible and runtime is active, runs OpenAI tool-calling to produce a structured decision
- Normalizes and clamps proposed prices into safe operating bounds
- Publishes `price-decisions` (and optionally `alerts`)

`services/inventory-service` (async worker service):

- Consumes `orders`
- Decrements stock and persists order events (idempotent by unique `event_id`)
- Publishes `inventory-updates` and `alerts` (LOW_STOCK)

`services/competitor-simulator`:

- Periodically persists competitor snapshots
- Publishes `price-changes` (keyed by `product_id:competitor_name`)
- Idles when no active runtime session exists

`services/demand-simulator`:

- Publishes `orders`
- Idles when no active runtime session exists

`frontend` (React/Vite):

- REST client against Dashboard API for catalog/analytics
- WebSocket client for live feed and product rooms

### 2) Data Model (PostgreSQL)

Core tables used by the operational surface (representative fields):

- `products`: `name`, `category`, `our_price`, `cost_price`, `stock_quantity`, `min_margin_percent`, `is_active`
- `competitor_prices`: `product_id`, `competitor_name`, `price`, `captured_at`
- `price_history`: `product_id`, `old_price`, `new_price`, `change_reason`, `decided_by`, `created_at`
- `agent_decisions`: `product_id`, `decision_type`, `reasoning`, `confidence_score`, `tools_used`, `execution_status`, `created_at`
- `order_events`: `event_id` (unique), `product_id`, `quantity`, `customer_region`, `created_at`
- `runtime_access_sessions`: `user_id`, `activated_at`, `expires_at`

### 3) Kafka Topic Contracts

All messages are JSON values. Producers serialize with `json.dumps(..., default=str)`, so `Decimal` fields (prices, percent deltas) are typically encoded as JSON strings. `request_id` is propagated and used for log correlation.

`price-changes` (producer: competitor-simulator; consumers: pricing-agent, dashboard-api live bridge)

```json
{
  "event_id": "uuid",
  "request_id": "uuid",
  "product_id": 123,
  "competitor_name": "FlipMart",
  "old_price": "999.99",
  "new_price": "974.99",
  "change_percent": "-2.5",
  "timestamp": "2026-05-17T12:34:56Z"
}
```

`orders` (producer: demand-simulator; consumer: inventory-service)

```json
{
  "event_id": "uuid",
  "request_id": "uuid",
  "product_id": 123,
  "quantity": 2,
  "customer_region": "Mumbai",
  "timestamp": "2026-05-17T12:34:56Z"
}
```

`inventory-updates` (producer: inventory-service; consumer: dashboard-api via DB reads + live bridge for UI)

```json
{
  "event_id": "uuid",
  "request_id": "uuid",
  "product_id": 123,
  "previous_stock": 20,
  "new_stock": 18,
  "change_reason": "ORDER",
  "timestamp": "2026-05-17T12:34:56Z"
}
```

`price-decisions` (producer: pricing-agent; consumers: dashboard-api live bridge + analytics via DB)

```json
{
  "event_id": "uuid",
  "request_id": "uuid",
  "product_id": 123,
  "decision_type": "PRICE_DROP | PRICE_HOLD | PRICE_INCREASE | REORDER_ALERT",
  "reasoning": "string",
  "confidence_score": 0.0,
  "tools_used": ["get_product_details"],
  "execution_status": "EXECUTED | SKIPPED | FAILED",
  "created_at": "2026-05-17T12:34:56Z",
  "source_event_id": "uuid",
  "proposed_price": 949.99
}
```

`alerts` (producer: inventory-service and pricing-agent; consumers: dashboard-api live bridge + UI)

```json
{
  "event_id": "uuid",
  "request_id": "uuid",
  "product_id": 123,
  "alert_type": "LOW_STOCK | REORDER_ALERT",
  "current_stock": 10,
  "threshold": 15,
  "reason": "string",
  "product_name": "optional string",
  "recommended_action": "optional string",
  "timestamp": "2026-05-17T12:34:56Z"
}
```

### 4) Key Runtime Flows (Sequence)

Competitor signal to pricing decision:

```mermaid
sequenceDiagram
    participant CS as Competitor Simulator
    participant K as Kafka
    participant PA as Pricing Agent
    participant DB as PostgreSQL
    participant API as Dashboard API
    participant FE as React Dashboard

    CS->>K: publish price-changes
    PA->>K: consume price-changes
    PA->>DB: load product + recent decisions (cooldown)
    PA->>PA: rule-engine fast path
    PA->>DB: tool calls (product/market/demand) + optional price update
    PA->>K: publish price-decisions (+ alerts)
    API->>K: consume (bridge) and broadcast via WS
    FE-->>API: WS receive live-feed/product room events
```

Demand order to inventory update:

```mermaid
sequenceDiagram
    participant DS as Demand Simulator
    participant K as Kafka
    participant IS as Inventory Service
    participant DB as PostgreSQL

    DS->>K: publish orders
    IS->>K: consume orders
    IS->>DB: decrement stock + insert order_events (idempotent by event_id)
    IS->>K: publish inventory-updates
    IS->>K: publish alerts (LOW_STOCK) when below threshold
```

### 5) Guardrails and Safety Mechanisms

- Margin floor enforced on product create/update (API) and on agent execution paths.
- Noise filter: ignore competitor changes below `MIN_SIGNIFICANT_PRICE_CHANGE_PERCENT`.
- Cooldown: ignore repricing for `PRICING_COOLDOWN_MINUTES` after a recent decision.
- Feedback-loop prevention: ignore competitor events that echo our own updates (source/competitor name/new_price checks).
- Bounded execution: per-action caps for drop/increase; clamping/normalization of oversized model proposals.
- Runtime gate: simulators and agent idle unless at least one active `runtime_access_sessions` row exists.

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)
![Kafka](https://img.shields.io/badge/Apache_Kafka-Event_Stream-231F20?logo=apachekafka&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-Live_Updates-1F2937)
![OpenAI](https://img.shields.io/badge/OpenAI-Tool_Calling-412991?logo=openai&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-Tested-0A9EDC?logo=pytest&logoColor=white)

---

## Core Features

- Real-time dashboard with pages for overview, products, decisions, alerts, and margin insights.
- Product drill-down with historical pricing and competitor snapshot context.
- WebSocket live feeds for global activity and per-product updates.
- Runtime session activation that turns the simulator + AI pipeline on for dashboard use.
- AI decision engine with OpenAI tool calling plus deterministic safety rules.
- Margin floors, competitor safety buffers, and capped per-action price changes.

---

## Quick Start

### Prerequisites

- Docker Desktop
- Node.js 18+
- Python 3.11+ for local testing
- OpenAI API key if you want LLM-backed pricing decisions

### Setup

Create `.env` from the template:

```bash
copy .env.example .env
# or
cp .env.example .env
```

Optional: set your OpenAI key in `.env`.

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o
```

### Start the backend stack

```bash
docker compose up --build
```

Demo mode runs the same stack with faster simulator timing:

```bash
docker compose --profile demo up --build
```

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### Local URLs

- Frontend: `http://localhost:5173`
- Dashboard API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Kafka UI: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

---

## Runtime Activation

The simulators and pricing agent stay idle until a runtime session is activated. The dashboard uses the runtime-session API to start a short-lived session, which lets you demo the system without leaving background activity running indefinitely.

- Session length: 8 minutes
- Global activation limit: 15 starts per day
- Header required by runtime endpoints: `x-user-id`

Key endpoints:

- `GET /api/runtime-session/status`
- `POST /api/runtime-session/start`

---

## Frontend Views

- `/` dashboard summary with KPI cards, live event feed, and top movers
- `/products` catalog view with sorting, filters, and competitor pricing context
- `/products/:productId` product detail with price history charts
- `/decisions` paginated decision history
- `/alerts` operational alerts
- `/insights/margin` margin and pricing health view

---

## API Overview

Base API is available on root, `/api`, and `/api/v1`.

**Products**
- `GET /products`
- `GET /products/{product_id}`
- `GET /products/{product_id}/price-history`
- `POST /products`
- `PUT /products/{product_id}`
- `DELETE /products/{product_id}`

**Dashboard**
- `GET /decisions`
- `GET /decisions/{decision_id}`
- `GET /analytics/summary`
- `GET /analytics/top-movers`

**Live feeds**
- `WS /ws/live-feed`
- `WS /ws/product/{product_id}`

---

## AI Pricing Flow

When a competitor price event arrives, the pricing agent:

1. Loads product details, market position, and demand trend with internal tools.
2. Applies hard business constraints such as minimum margin and cooldown rules.
3. Calls OpenAI for a structured pricing decision when AI mode is enabled.
4. Normalizes or overrides weak `HOLD` outcomes into safe actions when the market clearly supports repricing.
5. Rejects unsafe price moves that exceed configured caps or competitor safety ceilings.
6. Persists the decision and publishes updates to Kafka for the dashboard and downstream services.

If no `OPENAI_API_KEY` is configured, the service safely falls back instead of attempting live model calls.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | empty | Enables LLM-backed pricing decisions |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model used by the pricing agent |
| `DATABASE_URL` | `postgresql+asyncpg://smart_pricing:smart_pricing@postgres:5432/smart_pricing` | Shared PostgreSQL connection |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `ALLOWED_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | CORS allowlist for dashboard API |
| `LOW_STOCK_THRESHOLD` | `15` | Stock level used for alerts and pricing context |
| `MIN_SIGNIFICANT_PRICE_CHANGE_PERCENT` | `2` | Noise filter for competitor moves |
| `PRICING_COOLDOWN_MINUTES` | `10` in compose | Cooldown between repricing actions |
| `MAX_CONCURRENT_DECISIONS` | `3` | Pricing agent concurrency |
| `PROCESSING_QUEUE_SIZE` | `100` | In-memory queue size for pricing work |
| `SIMULATION_MIN_INTERVAL_SECONDS` | `30` | Competitor simulator base minimum interval |
| `SIMULATION_MAX_INTERVAL_SECONDS` | `60` | Competitor simulator base maximum interval |
| `SIMULATION_SPEED` | `1.0` | Competitor simulator speed multiplier |
| `DEMAND_SIMULATION_MIN_INTERVAL_SECONDS` | `30` | Demand simulator base minimum interval |
| `DEMAND_SIMULATION_MAX_INTERVAL_SECONDS` | `60` | Demand simulator base maximum interval |
| `DEMAND_SIMULATION_SPEED` | `1.0` | Demand simulator speed multiplier |
| `DEMO_SIMULATION_MIN_INTERVAL_SECONDS` | `5` | Competitor simulator demo minimum interval |
| `DEMO_SIMULATION_MAX_INTERVAL_SECONDS` | `20` | Competitor simulator demo maximum interval |
| `DEMO_SIMULATION_SPEED` | `2.0` | Competitor simulator demo speed |
| `DEMO_DEMAND_SIMULATION_MIN_INTERVAL_SECONDS` | `5` | Demand simulator demo minimum interval |
| `DEMO_DEMAND_SIMULATION_MAX_INTERVAL_SECONDS` | `20` | Demand simulator demo maximum interval |
| `DEMO_DEMAND_SIMULATION_SPEED` | `2.0` | Demand simulator demo speed |
| `INVENTORY_CONSUMER_GROUP` | `inventory-service` | Inventory service Kafka consumer group |
| `LOG_LEVEL` | `INFO` | Shared service log level |

---

## Project Structure

```text
PriceWise/
|-- docs/
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |-- context/
|   |   |-- hooks/
|   |   |-- pages/
|   |   |-- services/
|   |   `-- utils/
|   `-- package.json
|-- scripts/
|   |-- create-kafka-topics.sh
|   |-- setup-pricing-agent-test-scenarios.sql
|   `-- run-pricing-agent-test-scenarios.ps1
|-- services/
|   |-- competitor-simulator/
|   |-- dashboard-api/
|   |-- demand-simulator/
|   |-- inventory-service/
|   |-- pricing-agent/
|   `-- shared/
|-- docker-compose.yml
|-- docker-compose.test.yml
|-- requirements-test.txt
`-- README.md
```

---

## Running Tests

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

Run all tests:

```bash
pytest -q
```

Run specific suites:

```bash
pytest services/dashboard-api/tests -q
pytest services/pricing-agent/tests -q
```

---

## Why This Project Is Interesting

- It combines event-driven systems, simulation, and guarded LLM automation in one workflow.
- The AI agent is not allowed to price blindly; every action is checked against business constraints.
- The dashboard is useful as an operations surface, not just a log viewer.
- The runtime-session model makes demos controlled and repeatable.

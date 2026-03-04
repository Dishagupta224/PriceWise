# Smart Pricing Agent

An event-driven e-commerce pricing system with a live operations dashboard, Kafka-based simulators, inventory processing, and a pricing agent that combines deterministic guardrails with GPT tool calling.

## What it does

- Ingests competitor price changes and order demand events through Kafka
- Stores products, competitor snapshots, price history, and agent decisions in PostgreSQL
- Runs an inventory consumer that updates stock and emits low-stock alerts
- Runs a pricing agent that can hold, drop, increase prices, or raise reorder alerts
- Exposes a FastAPI backend for products, analytics, decisions, and live WebSocket feeds
- Provides a React dashboard for monitoring catalog health and pricing activity

## Current architecture

```text
PriceWise/
|-- docker-compose.yml
|-- scripts/
|   |-- create-kafka-topics.sh
|   |-- setup-pricing-agent-test-scenarios.sql
|   |-- run-pricing-agent-test-scenarios.ps1
|-- services/
|   |-- dashboard-api/
|   |-- competitor-simulator/
|   |-- demand-simulator/
|   |-- inventory-service/
|   |-- pricing-agent/
|   |-- shared/
|-- frontend/
```

## Services

### `dashboard-api`

FastAPI service that:

- seeds and initializes the database at startup
- serves product, analytics, and decision endpoints
- bridges Kafka events to WebSocket clients
- supports both global and product-specific live feeds

Main URLs:

- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Products: `http://localhost:8000/api/v1/products`
- Decisions: `http://localhost:8000/api/v1/decisions`
- Analytics summary: `http://localhost:8000/api/v1/analytics/summary`
- Top movers: `http://localhost:8000/api/v1/analytics/top-movers`
- Live feed WebSocket: `ws://localhost:8000/ws/live-feed`
- Product WebSocket: `ws://localhost:8000/ws/product/{product_id}`

### `competitor-simulator`

Publishes realistic competitor price-change events to Kafka and persists competitor price snapshots in PostgreSQL.

### `demand-simulator`

Publishes weighted order events to Kafka to simulate demand activity.

### `inventory-service`

Consumes order events, updates stock levels in PostgreSQL, emits inventory updates, and raises low-stock alerts.

### `pricing-agent`

Consumes `price-changes` events and decides whether to:

- `PRICE_DROP`
- `PRICE_HOLD`
- `PRICE_INCREASE`
- `REORDER_ALERT`

Behavior:

- runs a fast-path rule engine before GPT
- uses OpenAI tool calling when `OPENAI_API_KEY` is configured
- enforces guardrails for margin floors, max move size, and competitor safety ceilings
- falls back safely to `HOLD` when OpenAI is unavailable or a decision is unsafe
- writes decisions to the database and publishes decision/alert events to Kafka

### `frontend`

React + Vite dashboard with three main views:

- Dashboard: summary cards, top movers, and live event feed
- Products: sortable and filterable catalog with competitive pricing status
- Product Detail: price history chart, recent decisions, and product-specific live updates
- Decisions: paginated decision explorer with filters and detailed reasoning panels

Default dev URL:

- Frontend app: `http://localhost:5173`

## Event flow

1. `competitor-simulator` publishes a `price-changes` event.
2. `pricing-agent` consumes the event, applies rules, optionally calls GPT tools, and decides an action.
3. Price decisions are published to `price-decisions`; alerts go to `alerts`.
4. `dashboard-api` streams relevant Kafka events over WebSockets.
5. The frontend refreshes product tables, charts, and decision views in near real time.
6. `demand-simulator` publishes `orders`, and `inventory-service` turns them into stock updates and alerts.

## Kafka topics

Topics created automatically on startup:

- `price-changes`
- `orders`
- `inventory-updates`
- `price-decisions`
- `alerts`

Kafka UI:

- `http://localhost:8080`

## Local development

### Prerequisites

- Docker Desktop
- Node.js 18+ for the frontend
- PowerShell if you want to use the included scenario script on Windows

### Start the backend stack

```bash
docker compose up --build
```

This starts PostgreSQL, Kafka, Kafka UI, the dashboard API, both simulators, the inventory service, and the pricing agent.

### Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api`, `/health`, and `/ws` to `http://localhost:8000`.

## Environment

### Dashboard API

The API service reads values from `services/dashboard-api/.env.example`.

Important values:

- `DATABASE_URL`
- `API_TITLE`
- `API_VERSION`
- `ALLOWED_ORIGINS`

### Pricing agent

The pricing agent accepts these Docker Compose environment variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `LOW_STOCK_THRESHOLD`
- `MIN_SIGNIFICANT_PRICE_CHANGE_PERCENT`
- `PRICING_COOLDOWN_MINUTES`
- `MAX_CONCURRENT_DECISIONS`
- `PROCESSING_QUEUE_SIZE`
- `METRICS_LOG_INTERVAL_SECONDS`

If `OPENAI_API_KEY` is missing, the service still runs but safely defaults to `HOLD` instead of making GPT-backed price changes.

## Useful workflows

### Inspect the API

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Run deterministic pricing-agent test scenarios

The repository includes a fixture loader and event publisher for testing the pricing pipeline:

```powershell
.\scripts\run-pricing-agent-test-scenarios.ps1
```

This script:

- loads deterministic SQL fixtures into Postgres
- publishes two test `price-changes` events into Kafka
- lets you inspect pricing-agent behavior with:

```bash
docker compose logs -f pricing-agent
```

## Frontend pages

### Dashboard

- active product count
- decisions made today
- average margin and revenue impact
- active alerts and overpriced products
- live event feed
- top price movers in the last 24 hours

### Products

- category and stock filters
- client-side competitive status labels: `Winning`, `At Risk`, `Losing`
- sort by product attributes, pricing gap, stock, and margin

### Product detail

- current price, stock, and margin snapshot
- best competitor reference price
- price history chart for 7, 14, or 30 days
- recent pricing decisions
- product-specific live WebSocket updates

### Decisions

- date filtering
- product search
- confidence threshold filtering
- decision detail expansion with reasoning, tool usage, before/after pricing, and execution status

## Notes

- The backend currently seeds sample product data on startup.
- Product CRUD is available through the API.
- The dashboard API exposes routes with `/api`, `/api/v1`, and unprefixed variants for compatibility.

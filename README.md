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

## Architecture

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

    API[Dashboard API<br/>FastAPI + WebSocket bridge] <-->|queries| DB
    API <-->|consume + stream events| K

    FE[React Dashboard] <-->|REST + WebSocket| API
```

**Kafka topics**
- `price-changes`
- `orders`
- `inventory-updates`
- `price-decisions`
- `alerts`

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

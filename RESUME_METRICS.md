# PriceWise Resume Metrics (Source-of-Truth)

Use these numbers for resume/interview answers.

## Bullet 1: Kafka + FastAPI backend

- Kafka topics actually created by script: **5**
  - `price-changes`, `orders`, `inventory-updates`, `price-decisions`, `alerts`
  - Source: `scripts/create-kafka-topics.sh`
- Core pricing stream topics used by agent/dashboard live flow: **3**
  - `price-changes`, `price-decisions`, `alerts`
  - Source: `services/pricing-agent/app/main.py`, `services/dashboard-api/app/kafka_websocket_bridge.py`
- Docker Compose services:
  - **11 total defined** (includes optional `demo-profile`)
  - **10 default runtime services** (without `demo` profile)
  - Source: `docker-compose.yml`
- FastAPI endpoints (dashboard-api):
  - **13 REST endpoints** (12 route endpoints + `/health`)
  - **2 WebSocket endpoints**
  - **15 logical endpoints total**
  - Source: `services/dashboard-api/app/routes/*`, `services/dashboard-api/app/main.py`

## Bullet 2: AI pricing agent

- Rule-based prefilter checks (fast-path): **7 core checks**
  1. Missing `product_id`
  2. Unknown product
  3. Inactive product
  4. Echo/self-generated event detection
  5. Insignificant change filter (`< 2%`)
  6. Cooldown check (recent decision window)
  7. Stock zero -> direct reorder alert (bypass AI)
  - Source: `services/pricing-agent/app/rule_engine.py`
- Margin floor:
  - Product-level `min_margin_percent` default: **20%**
  - Source: `services/pricing-agent/app/models.py`
- Per-decision move caps:
  - Max drop: **5%**
  - Max increase: **8%**
  - Source: `services/pricing-agent/app/config.py`
- Cooldown + significance filters:
  - Cooldown: **4 minutes**
  - Significant change threshold: **2%**
  - Source: `services/pricing-agent/app/config.py`
- OpenAI call resilience:
  - Retries: **3 attempts**
  - Base delay: **1.5s**
  - Source: `services/pricing-agent/app/config.py`

## Bullet 3: React dashboard

- Route/views count: **6**
  - Dashboard, Products, Product Detail, Decisions, Alerts, Margin Insights
  - Source: `frontend/src/App.jsx`
- Dashboard core live UI blocks: **6**
  - 4 summary cards + live event feed + top movers table
  - Source: `frontend/src/pages/DashboardPage.jsx`
- Real-time transport:
  - WebSocket endpoints: `/ws/live-feed`, `/ws/product/{product_id}`
  - Source: `services/dashboard-api/app/routes/live.py`

## Runtime-only metrics you should measure on VM

These values are environment/data dependent, so run and fill exact numbers:

1. Decision records in audit table:

```bash
docker compose exec -T postgres psql -U smart_pricing -d smart_pricing -c "SELECT COUNT(*) AS total_decisions FROM agent_decisions;"
```

2. Typical recent run volume:

```bash
docker compose exec -T postgres psql -U smart_pricing -d smart_pricing -c "SELECT DATE(created_at) AS day, COUNT(*) FROM agent_decisions GROUP BY 1 ORDER BY 1 DESC LIMIT 7;"
```

3. Live-feed latency (quick method):
- Trigger one known price-change event.
- Note event timestamp in producer/log.
- Compare with first appearance in dashboard live feed.
- Report p50/p95 estimate (example style: "typically 0.8-1.7s in demo runs").

## Resume-safe wording (numbers-backed)

**Option A (conservative and accurate):**

`Built an event-driven pricing platform with Kafka (5 topics; 3 core real-time pricing streams), FastAPI, and PostgreSQL across 10 default Docker Compose services; exposed 13 REST + 2 WebSocket endpoints for live analytics and operations.`

`Implemented a hybrid AI pricing engine with a 7-check deterministic prefilter and strict guardrails (20% margin floor default, 5% max drop, 8% max increase, 4-min cooldown), with retry-backed OpenAI integration and safe HOLD fallback.`

`Delivered a React dashboard with 6 operator views and live WebSocket streaming for pricing decisions and alerts, backed by auditable decision history in PostgreSQL.`

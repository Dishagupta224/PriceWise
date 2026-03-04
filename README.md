# Smart Pricing Agent

Phase 1 scaffold for an event-driven e-commerce pricing platform. This phase provides the first backend service, `dashboard-api`, backed by PostgreSQL and seeded product data.

## Structure

```text
PriceWise/
|-- docker-compose.yml
|-- services/
|   |-- dashboard-api/
|   |   |-- Dockerfile
|   |   |-- requirements.txt
|   |   |-- .env.example
|   |   |-- start.sh
|   |   |-- app/
|   |   |   |-- __init__.py
|   |   |   |-- config.py
|   |   |   |-- database.py
|   |   |   |-- enums.py
|   |   |   |-- main.py
|   |   |   |-- models.py
|   |   |   |-- schemas.py
|   |   |   |-- seed.py
|   |   |   |-- wait_for_db.py
|   |   |   |-- routes/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- products.py
|   |-- competitor-simulator/
|   |   |-- Dockerfile
|   |   |-- requirements.txt
|   |   |-- start.sh
|   |   |-- app/
|   |   |   |-- __init__.py
|   |   |   |-- config.py
|   |   |   |-- database.py
|   |   |   |-- main.py
|   |   |   |-- models.py
|   |-- demand-simulator/
|   |   |-- Dockerfile
|   |   |-- requirements.txt
|   |   |-- start.sh
|   |   |-- app/
|   |   |   |-- __init__.py
|   |   |   |-- config.py
|   |   |   |-- database.py
|   |   |   |-- main.py
|   |   |   |-- models.py
|   |-- inventory-service/
|   |   |-- Dockerfile
|   |   |-- requirements.txt
|   |   |-- start.sh
|   |   |-- app/
|   |   |   |-- __init__.py
|   |   |   |-- config.py
|   |   |   |-- database.py
|   |   |   |-- main.py
|   |   |   |-- models.py
|   |-- pricing-agent/
|   |   |-- Dockerfile
|   |   |-- requirements.txt
|   |   |-- start.sh
|   |   |-- app/
|   |   |   |-- __init__.py
|   |   |   |-- agent_tools.py
|   |   |   |-- config.py
|   |   |   |-- enums.py
|   |   |   |-- main.py
|   |   |   |-- models.py
|   |   |   |-- rule_engine.py
|   |-- shared/
|   |   |-- __init__.py
|   |   |-- database.py
|   |   |-- kafka_utils.py
|-- frontend/
```

## Run

1. Start the stack:

   ```bash
   docker compose up --build
   ```

2. Open the API docs:

   - Swagger UI: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`
   - Products: `http://localhost:8000/api/v1/products`
   - Kafka UI: `http://localhost:8080`

The `dashboard-api` container waits for PostgreSQL, creates tables, seeds sample products, and then starts Uvicorn with auto-reload for development.
The `competitor-simulator` container continuously publishes realistic competitor price changes to Kafka and persists those snapshots in PostgreSQL.
The `demand-simulator` container continuously publishes weighted order events to Kafka.
The `inventory-service` container consumes orders, updates stock in PostgreSQL, emits inventory updates, and sends low-stock alerts.
The `pricing-agent` container currently provides the fast-path rule engine and async database tools that will back GPT tool-calling in the next step.

## Kafka

The Compose stack now includes:

- Zookeeper: coordinates broker metadata for this single-node development setup
- Kafka broker: stores event streams and exposes them on `localhost:9092`
- Kafka UI: visual topic browser on `http://localhost:8080`
- Kafka init job: creates required topics automatically on startup

Topics created automatically:

- `price-changes` with 3 partitions
- `orders` with 3 partitions
- `inventory-updates` with 3 partitions
- `price-decisions` with 3 partitions
- `alerts` with 1 partition

## Environment

The service reads `DATABASE_URL` from the environment. Docker Compose provides the container-safe value by default, while `.env.example` documents the local setup.

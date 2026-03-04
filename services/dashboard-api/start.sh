#!/bin/sh
set -e

cd /app
export PYTHONPATH=/app

echo "Waiting for PostgreSQL to become available..."
python -m app.wait_for_db

echo "Creating tables and seeding initial data..."
python -m app.seed

echo "Starting FastAPI with Uvicorn on port 8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

#!/bin/sh
set -e

cd /app
export PYTHONPATH=/app

exec python -m app.main

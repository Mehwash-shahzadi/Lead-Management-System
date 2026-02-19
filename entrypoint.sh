#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Seeding sample data..."
python -m app.scripts.seed

echo "Starting application..."
exec "$@"

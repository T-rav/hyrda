#!/bin/bash
set -e

echo "🚀 Starting InsightMesh Task Scheduler..."

# Run database migrations for task database
echo "📦 Running task database migrations..."
cd /app
alembic -c alembic.ini upgrade head

# Run database migrations for data database
echo "📦 Running data database migrations..."
alembic -c alembic_data.ini upgrade head

echo "✅ Migrations completed successfully"

# Start the Flask application
echo "🌐 Starting Flask application..."
exec python -u /app/app.py

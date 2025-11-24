#!/bin/bash
set -e

# Ensure edgar cache directory uses /app (not /root)
export HOME=/app
export EDGAR_LOCAL_DATA_DIR=/app/.edgar

echo "🚀 Starting InsightMesh Task Scheduler..."

# Run database migrations for task database
echo "📦 Running task database migrations..."
cd /app
alembic -c alembic.ini upgrade head

# Run database migrations for data database
echo "📦 Running data database migrations..."
alembic -c alembic_data.ini upgrade head

echo "✅ Migrations completed successfully"

# Start the Flask application with Gunicorn
echo "🌐 Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8081 --workers 4 --worker-class sync --timeout 120 --access-logfile - --error-logfile - app:app

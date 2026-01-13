#!/bin/bash
set -e

echo "Starting Agent Service..."

# Start FastAPI application with Gunicorn
# External agents (profile, meddic) are loaded as Python modules
# and served via the unified /api/agents/{name}/invoke endpoint
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    app:app

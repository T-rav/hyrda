#!/bin/sh
set -e

# Generate langgraph.json dynamically based on available agents
echo "Generating langgraph.json..."
python3 /app/generate_langgraph_config.py

# Internal services use HTTP - nginx handles SSL termination
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --forwarded-allow-ips '' \
    --access-logfile - \
    --error-logfile - \
    app:app

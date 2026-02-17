#!/bin/sh
set -e

# Generate langgraph.json dynamically based on available agents
echo "Generating langgraph.json..."
python3 /app/generate_langgraph_config.py

# SSL is optional - disable when behind a reverse proxy (nginx)
# Set USE_SSL=false in environment to disable

if [ "$USE_SSL" = "false" ]; then
    echo "Starting without SSL (USE_SSL=false)"
    exec gunicorn \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --timeout 120 \
        --forwarded-allow-ips '' \
        --access-logfile - \
        --error-logfile - \
        app:app
else
    echo "Starting with SSL"
    exec gunicorn \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --timeout 120 \
        --forwarded-allow-ips '' \
        --access-logfile - \
        --error-logfile - \
        --keyfile /app/ssl/agent-service-key.pem \
        --certfile /app/ssl/agent-service-cert.pem \
        app:app
fi

#!/bin/sh
set -e

# Generate SSL certificates using shared script
sh /app/shared/scripts/generate-ssl-certs.sh agent-service localhost agent-service 127.0.0.1 ::1

# Start Gunicorn with HTTPS
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --keyfile ssl/key.pem \
    --certfile ssl/cert.pem \
    app:app

#!/bin/sh
set -e

# SSL is optional - disable when behind a reverse proxy (nginx)
# Set USE_SSL=false in environment to disable

if [ "$USE_SSL" = "false" ]; then
    echo "Starting without SSL (USE_SSL=false)"
    exec uvicorn app:app --host 0.0.0.0 --port 6001 --workers 4
else
    echo "Starting with SSL"
    exec uvicorn app:app --host 0.0.0.0 --port 6001 --workers 4 \
        --ssl-keyfile /app/ssl/control-plane-key.pem \
        --ssl-certfile /app/ssl/control-plane-cert.pem
fi

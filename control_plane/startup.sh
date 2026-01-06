#!/bin/sh
set -e

# Generate self-signed SSL certificates if they don't exist
if [ ! -f "ssl/localhost.key" ] || [ ! -f "ssl/localhost.crt" ]; then
    echo "Generating self-signed SSL certificates..."
    mkdir -p ssl
    openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout ssl/localhost.key \
        -out ssl/localhost.crt \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=InsightMesh/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,DNS:control-plane,IP:127.0.0.1"
    echo "SSL certificates generated successfully"
else
    echo "SSL certificates already exist, skipping generation"
fi

# Start the FastAPI app with Uvicorn
exec uvicorn app:app --host 0.0.0.0 --port 6001 --workers 4 \
    --ssl-keyfile ssl/localhost.key \
    --ssl-certfile ssl/localhost.crt

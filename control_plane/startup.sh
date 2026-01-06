#!/bin/sh
set -e

# Generate SSL certificates if they don't exist
if [ ! -f "ssl/localhost.key" ] || [ ! -f "ssl/localhost.crt" ]; then
    mkdir -p ssl

    # Try to use mkcert if available (trusted certificates)
    if command -v mkcert >/dev/null 2>&1; then
        echo "Generating locally-trusted SSL certificates with mkcert..."
        cd ssl
        mkcert -install 2>/dev/null || true  # Install root CA (may already be installed)
        mkcert localhost control-plane 127.0.0.1 ::1
        mv localhost+3.pem localhost.crt
        mv localhost+3-key.pem localhost.key
        cd ..
        echo "Locally-trusted SSL certificates generated successfully (no browser warnings!)"
    else
        # Fallback to self-signed certificates (will show browser warning)
        echo "mkcert not found, generating self-signed SSL certificates..."
        echo "To avoid browser warnings, install mkcert: https://github.com/FiloSottile/mkcert"
        openssl req -x509 -newkey rsa:4096 -nodes \
            -keyout ssl/localhost.key \
            -out ssl/localhost.crt \
            -days 365 \
            -subj "/C=US/ST=State/L=City/O=InsightMesh/CN=localhost" \
            -addext "subjectAltName=DNS:localhost,DNS:control-plane,IP:127.0.0.1"
        echo "Self-signed SSL certificates generated (browser will show warning)"
    fi
else
    echo "SSL certificates already exist, skipping generation"
fi

# Start the FastAPI app with Uvicorn
exec uvicorn app:app --host 0.0.0.0 --port 6001 --workers 4 \
    --ssl-keyfile ssl/localhost.key \
    --ssl-certfile ssl/localhost.crt

#!/bin/sh
# Shared SSL certificate generation script using mkcert
# Usage: generate-ssl-certs.sh <service-name> <additional-domains...>
#
# Examples:
#   generate-ssl-certs.sh control-plane localhost 127.0.0.1
#   generate-ssl-certs.sh agent-service localhost agent-service 127.0.0.1

set -e

SERVICE_NAME="${1:-localhost}"
shift  # Remove first argument, rest are domains

# Default domains if none provided
if [ $# -eq 0 ]; then
    DOMAINS="localhost 127.0.0.1 ::1 ${SERVICE_NAME}"
else
    DOMAINS="$@"
fi

SSL_DIR="ssl"
CERT_FILE="${SSL_DIR}/cert.pem"
KEY_FILE="${SSL_DIR}/key.pem"

# Generate SSL certificates if they don't exist
if [ ! -f "${KEY_FILE}" ] || [ ! -f "${CERT_FILE}" ]; then
    mkdir -p "${SSL_DIR}"

    # Try to use mkcert if available (trusted certificates)
    if command -v mkcert >/dev/null 2>&1; then
        echo "🔐 Generating locally-trusted SSL certificates with mkcert for ${SERVICE_NAME}..."
        cd "${SSL_DIR}"

        # Install CA (idempotent - won't reinstall if already there)
        mkcert -install 2>/dev/null || true

        # Generate certificate for all domains
        mkcert ${DOMAINS}

        # Rename to standard names
        mv *.pem cert.pem 2>/dev/null || true
        mv *-key.pem key.pem 2>/dev/null || true

        cd ..
        echo "✅ Locally-trusted SSL certificates generated for ${SERVICE_NAME} (no browser warnings!)"
        echo "   Valid for: ${DOMAINS}"
    else
        # Fallback to self-signed certificates (will show browser warning)
        echo "⚠️  mkcert not found, generating self-signed SSL certificates for ${SERVICE_NAME}..."
        echo "   To avoid browser warnings, install mkcert: https://github.com/FiloSottile/mkcert"

        # Build SAN extension for all domains
        SAN=""
        for domain in ${DOMAINS}; do
            if echo "${domain}" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
                SAN="${SAN:+$SAN,}IP:${domain}"
            elif echo "${domain}" | grep -qE '^::'; then
                SAN="${SAN:+$SAN,}IP:${domain}"
            else
                SAN="${SAN:+$SAN,}DNS:${domain}"
            fi
        done

        openssl req -x509 -newkey rsa:4096 -nodes \
            -keyout "${KEY_FILE}" \
            -out "${CERT_FILE}" \
            -days 365 \
            -subj "/C=US/ST=State/L=City/O=InsightMesh/CN=${SERVICE_NAME}" \
            -addext "subjectAltName=${SAN}"

        echo "⚠️  Self-signed SSL certificates generated (browser will show warning)"
    fi
else
    echo "✓ SSL certificates already exist for ${SERVICE_NAME}, skipping generation"
fi

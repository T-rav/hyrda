#!/bin/bash
# Generate SSL certificates locally using mkcert for Docker services
set -e

echo "🔐 Setting up SSL certificates for local development..."

# Check if mkcert is installed
if ! command -v mkcert &> /dev/null; then
    echo "❌ mkcert is not installed!"
    echo ""
    echo "Install it with: brew install mkcert"
    echo "Then run: mkcert -install"
    echo ""
    exit 1
fi

# Check if mkcert CA is installed
if ! mkcert -CAROOT &> /dev/null; then
    echo "❌ mkcert CA is not installed!"
    echo ""
    echo "Run: mkcert -install"
    echo ""
    exit 1
fi

echo "✅ mkcert is installed and CA is trusted"

# Create SSL directory
SSL_DIR="$(dirname "$0")/../.ssl"
mkdir -p "$SSL_DIR"
cd "$SSL_DIR"

# Track if any certs were generated
CERTS_GENERATED=false

# Generate certificates for control-plane
if [ ! -f "control-plane-cert.pem" ] || [ ! -f "control-plane-key.pem" ]; then
    echo "📜 Generating certificate for control-plane (localhost:6001)..."
    mkcert -cert-file control-plane-cert.pem -key-file control-plane-key.pem \
        localhost 127.0.0.1 ::1 control-plane
    CERTS_GENERATED=true
else
    echo "✅ control-plane certificate already exists, skipping..."
fi

# Generate certificates for agent-service
if [ ! -f "agent-service-cert.pem" ] || [ ! -f "agent-service-key.pem" ]; then
    echo "📜 Generating certificate for agent-service (localhost:8000)..."
    mkcert -cert-file agent-service-cert.pem -key-file agent-service-key.pem \
        localhost 127.0.0.1 ::1 agent-service
    CERTS_GENERATED=true
else
    echo "✅ agent-service certificate already exists, skipping..."
fi

# Generate certificates for tasks service
if [ ! -f "tasks-cert.pem" ] || [ ! -f "tasks-key.pem" ]; then
    echo "📜 Generating certificate for tasks (localhost:5001)..."
    mkcert -cert-file tasks-cert.pem -key-file tasks-key.pem \
        localhost 127.0.0.1 ::1 tasks
    CERTS_GENERATED=true
else
    echo "✅ tasks certificate already exists, skipping..."
fi

# Generate certificates for qdrant
if [ ! -f "qdrant-cert.pem" ] || [ ! -f "qdrant-key.pem" ]; then
    echo "📜 Generating certificate for qdrant (localhost:6333)..."
    mkcert -cert-file qdrant-cert.pem -key-file qdrant-key.pem \
        localhost 127.0.0.1 ::1 qdrant
    CERTS_GENERATED=true
else
    echo "✅ qdrant certificate already exists, skipping..."
fi

# Generate certificates for LibreChat
if [ ! -f "librechat-cert.pem" ] || [ ! -f "librechat-key.pem" ]; then
    echo "📜 Generating certificate for LibreChat..."
    mkcert -cert-file librechat-cert.pem -key-file librechat-key.pem \
        localhost 127.0.0.1 ::1 librechat
    CERTS_GENERATED=true
else
    echo "✅ LibreChat certificate already exists, skipping..."
fi

# Copy mkcert CA certificate for Docker containers
if [ ! -f "mkcert-ca.crt" ]; then
    echo "📜 Copying mkcert CA certificate for container trust..."
    cp "$(mkcert -CAROOT)/rootCA.pem" mkcert-ca.crt
    CERTS_GENERATED=true
else
    echo "✅ mkcert CA certificate already exists, skipping..."
fi

cd - > /dev/null

echo ""
if [ "$CERTS_GENERATED" = true ]; then
    echo "✅ SSL certificates generated successfully!"
else
    echo "✅ SSL certificates already exist, no generation needed!"
fi
echo ""
echo "Certificates are stored in: $SSL_DIR"
echo "  - control-plane: control-plane-cert.pem, control-plane-key.pem"
echo "  - agent-service: agent-service-cert.pem, agent-service-key.pem"
echo "  - tasks: tasks-cert.pem, tasks-key.pem"
echo "  - qdrant: qdrant-cert.pem, qdrant-key.pem"
echo "  - librechat: librechat-cert.pem, librechat-key.pem"
echo "  - mkcert CA: mkcert-ca.crt (for Docker container trust)"
echo ""
echo "These certificates are signed by your local mkcert CA and will be trusted by your browser."
echo "The mkcert-ca.crt file will be installed in Docker containers for SSL verification."
echo ""

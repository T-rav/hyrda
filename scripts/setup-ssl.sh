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

# Generate certificates for control-plane
echo "📜 Generating certificate for control-plane (localhost:6001)..."
cd "$SSL_DIR"
mkcert -cert-file control-plane-cert.pem -key-file control-plane-key.pem \
    localhost 127.0.0.1 ::1 control-plane

# Generate certificates for agent-service
echo "📜 Generating certificate for agent-service (localhost:8000)..."
mkcert -cert-file agent-service-cert.pem -key-file agent-service-key.pem \
    localhost 127.0.0.1 ::1 agent-service

# Generate certificates for tasks service
echo "📜 Generating certificate for tasks (localhost:5001)..."
mkcert -cert-file tasks-cert.pem -key-file tasks-key.pem \
    localhost 127.0.0.1 ::1 tasks

# Generate certificates for qdrant
echo "📜 Generating certificate for qdrant (localhost:6333)..."
mkcert -cert-file qdrant-cert.pem -key-file qdrant-key.pem \
    localhost 127.0.0.1 ::1 qdrant

# Copy mkcert CA certificate for Docker containers
echo "📜 Copying mkcert CA certificate for container trust..."
cp "$(mkcert -CAROOT)/rootCA.pem" mkcert-ca.crt

cd - > /dev/null

echo ""
echo "✅ SSL certificates generated successfully!"
echo ""
echo "Certificates are stored in: $SSL_DIR"
echo "  - control-plane: control-plane-cert.pem, control-plane-key.pem"
echo "  - agent-service: agent-service-cert.pem, agent-service-key.pem"
echo "  - tasks: tasks-cert.pem, tasks-key.pem"
echo "  - qdrant: qdrant-cert.pem, qdrant-key.pem"
echo "  - mkcert CA: mkcert-ca.crt (for Docker container trust)"
echo ""
echo "These certificates are signed by your local mkcert CA and will be trusted by your browser."
echo "The mkcert-ca.crt file will be installed in Docker containers for SSL verification."
echo ""

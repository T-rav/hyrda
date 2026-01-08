#!/bin/bash
set -e

# trust-local-certs.sh
# Automates trusting self-signed SSL certificates on macOS
# Run after initial setup: ./scripts/trust-local-certs.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SSL_DIR="$PROJECT_ROOT/.ssl"

echo "🔐 InsightMesh Certificate Trust Setup"
echo "======================================"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ Error: This script is for macOS only"
    echo "   On Linux, certificates are installed via Docker (update-ca-certificates)"
    exit 1
fi

# Check if .ssl directory exists
if [ ! -d "$SSL_DIR" ]; then
    echo "❌ Error: SSL directory not found at $SSL_DIR"
    echo "   Please generate certificates first"
    exit 1
fi

# Count certificates
CERT_COUNT=$(find "$SSL_DIR" -name "*-cert.pem" 2>/dev/null | wc -l | tr -d ' ')

if [ "$CERT_COUNT" -eq 0 ]; then
    echo "❌ Error: No certificates found in $SSL_DIR"
    echo "   Please generate certificates first"
    exit 1
fi

echo "Found $CERT_COUNT certificates to trust:"
echo ""

# List certificates
find "$SSL_DIR" -name "*-cert.pem" | while read -r cert; do
    basename "$cert"
done

echo ""
echo "This script will add these certificates to your macOS System Keychain."
echo "You will be prompted for your password (sudo required)."
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled by user"
    exit 1
fi

echo ""
echo "🔓 Adding certificates to System Keychain..."
echo ""

SUCCESS_COUNT=0
SKIP_COUNT=0
ERROR_COUNT=0

# Add each certificate
find "$SSL_DIR" -name "*-cert.pem" | while read -r cert; do
    CERT_NAME=$(basename "$cert")

    # Check if certificate is already trusted
    if security find-certificate -c "$CERT_NAME" /Library/Keychains/System.keychain &>/dev/null; then
        echo "⏩ Skipped: $CERT_NAME (already trusted)"
        SKIP_COUNT=$((SKIP_COUNT + 1))
    else
        echo "📥 Adding: $CERT_NAME"

        if sudo security add-trusted-cert -d -r trustRoot \
            -k /Library/Keychains/System.keychain "$cert" 2>/dev/null; then
            echo "✅ Added: $CERT_NAME"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo "❌ Failed: $CERT_NAME"
            ERROR_COUNT=$((ERROR_COUNT + 1))
        fi
    fi
    echo ""
done

echo ""
echo "======================================"
echo "📊 Summary:"
echo "   ✅ Added: $SUCCESS_COUNT"
echo "   ⏩ Skipped: $SKIP_COUNT (already trusted)"
echo "   ❌ Failed: $ERROR_COUNT"
echo ""

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "⚠️  Some certificates failed to install"
    echo "   You may need to remove conflicting certificates first:"
    echo "   sudo security delete-certificate -c <cert-name> /Library/Keychains/System.keychain"
    exit 1
fi

echo "✅ All certificates are now trusted on this machine!"
echo ""
echo "🔍 Verify with: security find-certificate -a /Library/Keychains/System.keychain | grep -A5 InsightMesh"
echo ""
echo "🗑️  To remove certificates later:"
echo "   ./scripts/remove-local-certs.sh"

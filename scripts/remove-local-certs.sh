#!/bin/bash
set -e

# remove-local-certs.sh
# Removes InsightMesh self-signed SSL certificates from macOS System Keychain
# Run when cleaning up: ./scripts/remove-local-certs.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SSL_DIR="$PROJECT_ROOT/.ssl"

echo "🗑️  InsightMesh Certificate Removal"
echo "======================================"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ Error: This script is for macOS only"
    exit 1
fi

# Find InsightMesh certificates in System Keychain
CERTS_TO_REMOVE=$(security find-certificate -a /Library/Keychains/System.keychain | \
    grep -B5 "InsightMesh" | grep "alis" | cut -d'"' -f2 || true)

if [ -z "$CERTS_TO_REMOVE" ]; then
    echo "ℹ️  No InsightMesh certificates found in System Keychain"
    exit 0
fi

echo "Found the following InsightMesh certificates:"
echo ""
echo "$CERTS_TO_REMOVE"
echo ""
echo "This will remove these certificates from your System Keychain."
echo "You will be prompted for your password (sudo required)."
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled by user"
    exit 1
fi

echo ""
echo "🗑️  Removing certificates..."
echo ""

SUCCESS_COUNT=0
ERROR_COUNT=0

# Remove each certificate
echo "$CERTS_TO_REMOVE" | while read -r cert_name; do
    echo "🗑️  Removing: $cert_name"

    if sudo security delete-certificate -c "$cert_name" \
        /Library/Keychains/System.keychain 2>/dev/null; then
        echo "✅ Removed: $cert_name"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "❌ Failed: $cert_name"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    fi
    echo ""
done

echo ""
echo "======================================"
echo "📊 Summary:"
echo "   ✅ Removed: $SUCCESS_COUNT"
echo "   ❌ Failed: $ERROR_COUNT"
echo ""

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "⚠️  Some certificates failed to remove"
    echo "   You may need to remove them manually via Keychain Access.app"
    exit 1
fi

echo "✅ All InsightMesh certificates removed!"

#!/bin/bash
# Production Secret Validation Script
# Ensures production environment doesn't use default/weak secrets
#
# Usage: Run this script before starting LibreChat in production
# Exit codes:
#   0 - All secrets are valid
#   1 - Invalid secrets detected (production blocked)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "LibreChat Production Secret Validation"
echo "========================================"
echo ""

# Detect environment
ENVIRONMENT="${ENVIRONMENT:-development}"
echo "Environment: $ENVIRONMENT"
echo ""

# Only validate in production
if [[ "$ENVIRONMENT" != "production" ]]; then
    echo -e "${GREEN}✓ Non-production environment detected - skipping validation${NC}"
    exit 0
fi

echo -e "${YELLOW}⚠ Production environment detected - validating secrets...${NC}"
echo ""

# Validation flags
HAS_ERRORS=0

# Function to validate a secret
validate_secret() {
    local SECRET_NAME=$1
    local SECRET_VALUE=$2
    local FORBIDDEN_PATTERNS=$3

    echo -n "Checking $SECRET_NAME... "

    # Check if secret is set
    if [[ -z "$SECRET_VALUE" ]]; then
        echo -e "${RED}✗ FAIL - Not set${NC}"
        HAS_ERRORS=1
        return 1
    fi

    # Check if secret matches forbidden patterns
    for PATTERN in $FORBIDDEN_PATTERNS; do
        if [[ "$SECRET_VALUE" == *"$PATTERN"* ]]; then
            echo -e "${RED}✗ FAIL - Contains forbidden pattern: '$PATTERN'${NC}"
            HAS_ERRORS=1
            return 1
        fi
    done

    # Check secret length (should be at least 32 characters for production)
    if [[ ${#SECRET_VALUE} -lt 32 ]]; then
        echo -e "${RED}✗ FAIL - Too short (${#SECRET_VALUE} chars, minimum 32)${NC}"
        HAS_ERRORS=1
        return 1
    fi

    echo -e "${GREEN}✓ OK${NC}"
    return 0
}

# Validate JWT_SECRET
validate_secret "JWT_SECRET" "$JWT_SECRET" "change-in-production insightmesh-librechat default test"

# Validate JWT_REFRESH_SECRET
validate_secret "JWT_REFRESH_SECRET" "$JWT_REFRESH_SECRET" "change-in-production insightmesh-librechat default test"

# Validate that secrets are different
echo -n "Checking JWT secrets are unique... "
if [[ "$JWT_SECRET" == "$JWT_REFRESH_SECRET" ]]; then
    echo -e "${RED}✗ FAIL - JWT_SECRET and JWT_REFRESH_SECRET must be different${NC}"
    HAS_ERRORS=1
else
    echo -e "${GREEN}✓ OK${NC}"
fi

echo ""

# Final result
if [[ $HAS_ERRORS -eq 0 ]]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All secrets are valid for production${NC}"
    echo -e "${GREEN}========================================${NC}"
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ SECRET VALIDATION FAILED${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}To generate secure secrets, run:${NC}"
    echo ""
    echo "  export JWT_SECRET=\$(openssl rand -base64 32)"
    echo "  export JWT_REFRESH_SECRET=\$(openssl rand -base64 32)"
    echo ""
    echo -e "${YELLOW}Or add to your .env file:${NC}"
    echo ""
    echo "  JWT_SECRET=\$(openssl rand -base64 32)"
    echo "  JWT_REFRESH_SECRET=\$(openssl rand -base64 32)"
    echo ""
    exit 1
fi

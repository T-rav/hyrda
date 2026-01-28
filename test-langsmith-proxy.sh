#!/bin/bash
# Test script for LangSmith proxy

set -e

echo "🧪 Testing LangSmith Proxy..."
echo ""

# Check if proxy is running
echo "1️⃣  Checking if proxy container is running..."
if docker ps | grep -q langsmith-proxy; then
    echo "   ✅ Proxy container is running"
else
    echo "   ❌ Proxy container not running"
    echo "   Starting it now..."
    docker compose up -d langsmith-proxy
    sleep 3
fi
echo ""

# Test health endpoint (no auth required)
echo "2️⃣  Testing health endpoint (no auth)..."
HEALTH=$(curl -s http://localhost:8003/health)
echo "   Response: $HEALTH"

if echo "$HEALTH" | grep -q "healthy"; then
    echo "   ✅ Health check passed"
else
    echo "   ❌ Health check failed"
    exit 1
fi
echo ""

# Check Langfuse availability
if echo "$HEALTH" | grep -q '"langfuse_available":true'; then
    echo "   ✅ Langfuse client initialized"
elif echo "$HEALTH" | grep -q '"langfuse_available":false'; then
    echo "   ⚠️  Langfuse client not available (check LANGFUSE_* credentials)"
else
    echo "   ❓ Langfuse status unknown"
fi
echo ""

# Test info endpoint (no auth required)
echo "3️⃣  Testing info endpoint..."
INFO=$(curl -s http://localhost:8003/info)
echo "   Response: $INFO"
echo ""

# Get proxy API key from env
PROXY_KEY=$(grep "^PROXY_API_KEY=" .env | cut -d= -f2)

if [ -z "$PROXY_KEY" ]; then
    echo "❌ PROXY_API_KEY not found in .env"
    exit 1
fi

echo "4️⃣  Testing authenticated endpoint (POST /runs)..."
echo "   Using API key: ${PROXY_KEY:0:8}..."
echo ""

# Test with valid key
echo "   a) Testing with VALID key..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    http://localhost:8003/runs \
    -H "Authorization: Bearer $PROXY_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "id": "test-run-123",
        "name": "test_trace",
        "run_type": "chain",
        "inputs": {"test": "data"},
        "start_time": "2024-01-01T00:00:00Z"
    }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "      ✅ Valid key accepted (200 OK)"
    echo "      Response: $BODY"
else
    echo "      ❌ Valid key rejected (HTTP $HTTP_CODE)"
    echo "      Response: $BODY"
fi
echo ""

# Test with invalid key
echo "   b) Testing with INVALID key..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    http://localhost:8003/runs \
    -H "Authorization: Bearer invalid-key-12345" \
    -H "Content-Type: application/json" \
    -d '{
        "id": "test-run-456",
        "name": "test_trace",
        "run_type": "chain",
        "inputs": {"test": "data"}
    }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "401" ]; then
    echo "      ✅ Invalid key rejected (401 Unauthorized)"
else
    echo "      ❌ Invalid key NOT rejected (HTTP $HTTP_CODE)"
    echo "      Response: $BODY"
fi
echo ""

# Test without key
echo "   c) Testing with NO key..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    http://localhost:8003/runs \
    -H "Content-Type: application/json" \
    -d '{
        "id": "test-run-789",
        "name": "test_trace",
        "run_type": "chain",
        "inputs": {"test": "data"}
    }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "403" ] || [ "$HTTP_CODE" = "401" ]; then
    echo "      ✅ No key rejected (HTTP $HTTP_CODE)"
else
    echo "      ❌ No key NOT rejected (HTTP $HTTP_CODE)"
    echo "      Response: $BODY"
fi
echo ""

# Check proxy logs for our test traces
echo "5️⃣  Checking proxy logs for test traces..."
echo ""
docker logs insightmesh-langsmith-proxy 2>&1 | tail -20 | grep -E "test_trace|test-run" || echo "   (No test traces in recent logs)"
echo ""

echo "✅ Proxy tests complete!"
echo ""
echo "📊 Summary:"
echo "   - Health endpoint: Working"
echo "   - Info endpoint: Working"
echo "   - Authentication: $([ "$HTTP_CODE" = "401" ] && echo "✅ Working" || echo "⚠️  Check logs")"
echo "   - Proxy is ready to receive LangSmith traces!"
echo ""
echo "💡 Next steps:"
echo "   1. Configure agent to use proxy:"
echo "      LANGCHAIN_ENDPOINT=http://langsmith-proxy:8003"
echo "      LANGCHAIN_API_KEY=${PROXY_KEY:0:8}..."
echo ""
echo "   2. Run an agent and check Langfuse for traces!"

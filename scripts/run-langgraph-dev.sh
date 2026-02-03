#!/bin/bash
# Run LangGraph dev mode with Studio UI on port 9000
# Regular agent-service continues running on port 8000

set -e

DEV_PORT=9000

echo "🚀 Starting LangGraph dev mode on port ${DEV_PORT}..."
echo ""

# Check if port 9000 is free
if lsof -i :${DEV_PORT} >/dev/null 2>&1; then
    echo "❌ Port ${DEV_PORT} is already in use"
    exit 1
fi

# Install langgraph-cli if needed
echo "1. Installing langgraph-cli..."
docker exec insightmesh-agent-service pip install "langgraph-cli[inmem]" -q 2>/dev/null || true

# Regenerate langgraph.json with correct dependencies
echo "2. Regenerating langgraph.json..."
docker exec insightmesh-agent-service python3 /app/generate_langgraph_config.py

echo ""
echo "3. Starting LangGraph dev server on port ${DEV_PORT}..."
echo ""
echo "   API:        http://localhost:${DEV_PORT}"
echo "   Studio UI:  https://smith.langchain.com/studio/?baseUrl=http://localhost:${DEV_PORT}"
echo "   API Docs:   http://localhost:${DEV_PORT}/docs"
echo ""
echo "   Regular agent-service still running on port 8000"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

# Run dev server on port 9000
docker exec -it insightmesh-agent-service sh -c "export PATH=\"/home/appuser/.local/bin:\$PATH\" && cd /app && langgraph dev --host 0.0.0.0 --port ${DEV_PORT}"

echo ""
echo "✅ LangGraph dev server stopped"

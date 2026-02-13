#!/bin/sh

# Start Milvus vector store for claude-context MCP server
echo "Starting Milvus vector store..."
docker compose -f dx/milvus/docker-compose.yml up -d

# Wait for Milvus to be healthy
echo "Waiting for Milvus to be ready..."
timeout=90
while [ $timeout -gt 0 ]; do
    if curl -sf http://localhost:9091/healthz >/dev/null 2>&1; then
        echo "Milvus is ready!"
        break
    fi
    sleep 2
    timeout=$((timeout - 2))
done

if [ $timeout -le 0 ]; then
    echo "Warning: Milvus may not be ready, continuing anyway..."
fi

claude -c --dangerously-skip-permissions

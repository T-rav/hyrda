#!/bin/bash

set -e  # Exit on any error

echo "🚀 Starting dependencies for AI Slack Bot..."
echo "=========================================="

# Navigate to project root
BOT_DIR="/Users/travisfrisinger/Documents/projects/ai-slack-bot"
cd "$BOT_DIR"

# Function to check if Docker is running
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        echo "❌ Docker is not running. Please start Docker first."
        exit 1
    fi

    echo "✅ Docker is running"
}

# Function to check if a container is running
is_container_running() {
    local container_name="$1"
    docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"
}

# Function to start a Docker Compose service
start_service() {
    local compose_file="$1"
    local service_name="$2"
    local container_name="$3"
    local description="$4"

    if [ ! -f "$compose_file" ]; then
        echo "⚠️  $compose_file not found, skipping $description"
        return
    fi

    if is_container_running "$container_name"; then
        echo "✅ $description is already running"
    else
        echo "🔄 Starting $description..."
        if docker compose -f "$compose_file" up -d "$service_name"; then
            echo "✅ $description started successfully"
            sleep 3  # Wait for service to initialize
        else
            echo "❌ Failed to start $description"
            exit 1
        fi
    fi
}

# Function to start Redis
start_redis() {
    if is_container_running "redis"; then
        echo "✅ Redis is already running"
        return
    fi

    echo "🔄 Starting Redis..."
    if docker run -d --name redis -p 6379:6379 redis:alpine; then
        echo "✅ Redis started successfully"
        sleep 2
    elif docker start redis; then
        echo "✅ Existing Redis container restarted"
        sleep 2
    else
        echo "❌ Failed to start Redis"
        exit 1
    fi
}

# Check Docker
check_docker

echo ""
echo "🔧 Starting core services..."
echo "============================"

# Start Elasticsearch (required for hybrid RAG)
start_service "docker-compose.elasticsearch.yml" "elasticsearch" "ai-slack-elasticsearch" "Elasticsearch"

# Start Redis (required for caching)
start_redis

echo ""
echo "🎯 All dependencies are running!"
echo "================================"
echo "✅ Elasticsearch: http://localhost:9200"
echo "✅ Redis: localhost:6379"
echo ""
echo "📋 Next steps:"
echo "  • Run the bot: ./start_bot.sh"
echo "  • Ingest documents: cd ingest && python main.py --folder-id YOUR_FOLDER_ID"
echo "  • Test hybrid search: Check bot responses for improved quality"

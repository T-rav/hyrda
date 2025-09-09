#!/bin/bash

set -e  # Exit on any error

echo "🚀 Starting AI Slack Bot with RAG capabilities..."
echo "======================================"

# Navigate to the project root directory
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

# Function to start a Docker Compose service if not running
start_service_if_needed() {
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
        if docker compose -f "$compose_file" up -d "$service_name" 2>/dev/null; then
            echo "✅ $description started successfully"
            # Wait a moment for the service to initialize
            sleep 2
        else
            echo "⚠️  Failed to start $description, but continuing..."
        fi
    fi
}

# Function to check if Redis is accessible
check_redis() {
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping &> /dev/null; then
            echo "✅ Redis is accessible"
            return 0
        fi
    fi
    return 1
}

# Function to start Redis container if needed
start_redis_if_needed() {
    if check_redis; then
        return
    fi

    if is_container_running "redis"; then
        echo "✅ Redis container is running"
        return
    fi

    echo "🔄 Starting Redis container..."
    if docker run -d --name redis -p 6379:6379 redis:alpine &> /dev/null; then
        echo "✅ Redis container started successfully"
        sleep 2
    elif docker start redis &> /dev/null; then
        echo "✅ Existing Redis container restarted"
        sleep 2
    else
        echo "⚠️  Could not start Redis, but continuing..."
    fi
}

# Check Docker availability
check_docker

echo ""
echo "🔍 Checking required services..."
echo "================================"

# Start Elasticsearch for hybrid RAG (if hybrid is enabled in .env)
if grep -q "HYBRID_ENABLED=true" .env 2>/dev/null; then
    start_service_if_needed "docker-compose.elasticsearch.yml" "elasticsearch" "ai-slack-elasticsearch" "Elasticsearch (Hybrid RAG)"
fi

# Start Redis for caching (if cache is enabled in .env)
if grep -q "CACHE_ENABLED=true" .env 2>/dev/null || grep -q "CACHE_REDIS_URL" .env 2>/dev/null; then
    start_redis_if_needed
fi

# Optional: Start monitoring services if they exist and are configured
if [ -f "docker-compose.monitoring.yml" ] && grep -q "PROMETHEUS\|GRAFANA" .env 2>/dev/null; then
    start_service_if_needed "docker-compose.monitoring.yml" "prometheus" "prometheus" "Monitoring (Prometheus)"
fi

echo ""
echo "🤖 Starting Slack Bot..."
echo "========================"

# Navigate to the bot directory
cd "$BOT_DIR/bot"

# Check if virtual environment exists
if [ ! -d "../venv" ]; then
    echo "❌ Virtual environment not found at ../venv"
    echo "Please run: make install"
    exit 1
fi

# Activate virtual environment
source ../venv/bin/activate

# Check if required environment variables are set
if [ ! -f "../.env" ]; then
    echo "❌ .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Check critical environment variables
if ! grep -q "SLACK_BOT_TOKEN=xoxb-" ../.env 2>/dev/null; then
    echo "⚠️  SLACK_BOT_TOKEN not configured in .env file"
fi

if ! grep -q "LLM_API_KEY" ../.env 2>/dev/null; then
    echo "⚠️  LLM_API_KEY not configured in .env file"
fi

echo "✅ Environment configured"
echo "✅ Virtual environment activated"
echo ""
echo "🎯 Launching AI Slack Bot..."
echo "============================"

# Start the bot
exec python app.py

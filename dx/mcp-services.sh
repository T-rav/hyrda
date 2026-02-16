#!/usr/bin/env bash
#
# Claude MCP Services Manager
# Manages services required by Claude Code MCP servers
#
# Usage:
#   ./dx/mcp-services.sh start    # Start all MCP-required services
#   ./dx/mcp-services.sh stop     # Stop all MCP-required services
#   ./dx/mcp-services.sh restart  # Restart all MCP-required services
#   ./dx/mcp-services.sh status   # Check status of all services
#   ./dx/mcp-services.sh logs     # View logs from all services
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MILVUS_DIR="$SCRIPT_DIR/milvus"
CODEQL_MCP_DIR="$SCRIPT_DIR/codeql-mcp"
CODEQL_PID_FILE="$SCRIPT_DIR/.codeql-mcp.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Install with: brew install docker"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker Desktop."
        exit 1
    fi
}

start_services() {
    log_info "Starting MCP required services..."
    echo

    check_docker

    # Start Milvus (required for claude-context MCP server)
    log_info "Starting Milvus vector database..."
    cd "$MILVUS_DIR"

    if docker compose up -d; then
        log_success "Milvus started successfully"
    else
        log_error "Failed to start Milvus"
        exit 1
    fi

    cd "$PROJECT_ROOT"
    echo

    # Wait for Milvus to be healthy
    log_info "Waiting for Milvus to be ready..."
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if docker exec milvus-standalone curl -f http://localhost:9091/healthz &> /dev/null; then
            log_success "Milvus is ready"
            break
        fi

        attempt=$((attempt + 1))
        if [ $attempt -eq $max_attempts ]; then
            log_error "Milvus failed to become healthy after ${max_attempts} attempts"
            exit 1
        fi

        echo -n "."
        sleep 2
    done

    echo
    echo

    # Start CodeQL MCP server
    if [ -d "$CODEQL_MCP_DIR/.venv" ]; then
        log_info "Starting CodeQL MCP server..."

        # Check if already running
        if [ -f "$CODEQL_PID_FILE" ] && kill -0 $(cat "$CODEQL_PID_FILE") 2>/dev/null; then
            log_warning "CodeQL already running (PID: $(cat "$CODEQL_PID_FILE"))"
        else
            nohup bash -c "cd $CODEQL_MCP_DIR && source .venv/bin/activate && python server.py" > "$SCRIPT_DIR/.codeql-mcp.log" 2>&1 &
            echo $! > "$CODEQL_PID_FILE"
            sleep 2  # Wait for server to start
            log_success "CodeQL MCP server started (PID: $!)"
        fi
        echo
    fi

    log_success "All MCP services are running!"
    echo
    echo "Services:"
    echo "  ✓ Milvus (claude-context semantic code search)"
    echo "    - Milvus API: http://localhost:19530"
    echo "    - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
    if [ -f "$CODEQL_PID_FILE" ]; then
        echo "  ✓ CodeQL (deep code navigation)"
        echo "    - SSE Endpoint: http://127.0.0.1:8000/sse"
    fi
    echo
    echo "Next steps:"
    echo "  1. Start/restart Claude Code to connect to MCP servers"
    echo "  2. Try semantic navigation: 'Show all implementations of VectorStore protocol'"
    echo "  3. Try code search: 'Find all authentication code in the codebase'"
    echo "  4. Create CodeQL database: codeql database create --language=python codeql-db"
}

stop_services() {
    log_info "Stopping MCP required services..."
    echo

    check_docker

    # Stop CodeQL MCP server
    if [ -f "$CODEQL_PID_FILE" ]; then
        log_info "Stopping CodeQL MCP server..."
        PID=$(cat "$CODEQL_PID_FILE")
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            rm "$CODEQL_PID_FILE"
            log_success "CodeQL stopped"
        else
            log_warning "CodeQL not running (stale PID)"
            rm "$CODEQL_PID_FILE"
        fi
        echo
    fi

    # Stop Milvus
    log_info "Stopping Milvus..."
    cd "$MILVUS_DIR"

    if docker compose down; then
        log_success "Milvus stopped successfully"
    else
        log_warning "Some issues stopping Milvus (may already be stopped)"
    fi

    cd "$PROJECT_ROOT"
    echo

    log_success "All MCP services stopped"
}

restart_services() {
    log_info "Restarting MCP required services..."
    echo

    stop_services
    echo
    start_services
}

status_services() {
    log_info "Checking MCP service status..."
    echo

    check_docker

    # Check CodeQL
    if [ -f "$CODEQL_PID_FILE" ]; then
        PID=$(cat "$CODEQL_PID_FILE")
        if kill -0 $PID 2>/dev/null; then
            echo "CodeQL MCP Server: ✓ Running (PID: $PID)"
            echo "  Endpoint: http://127.0.0.1:8000/sse"
        else
            echo "CodeQL MCP Server: ✗ Not running"
        fi
    else
        echo "CodeQL MCP Server: ✗ Not running"
    fi
    echo

    # Check Milvus
    cd "$MILVUS_DIR"
    echo "Milvus services:"
    docker compose ps

    echo
    echo "Container health:"
    docker ps --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    cd "$PROJECT_ROOT"
}

logs_services() {
    log_info "Showing logs from MCP services..."
    echo

    local service="${1:-all}"

    case "$service" in
        milvus|all|*)
            log_info "Milvus logs (Ctrl+C to stop):"
            cd "$MILVUS_DIR"
            docker compose logs -f
            ;;
    esac
}

show_help() {
    cat << EOF
Claude MCP Services Manager

Manages services required by Claude Code MCP servers.

USAGE:
    ./dx/mcp-services.sh <command>

COMMANDS:
    start                Start all MCP-required services
    stop                 Stop all MCP-required services
    restart              Restart all MCP-required services
    status               Check status of all services
    logs                 View Milvus logs
    help                 Show this help message

SERVICES MANAGED:
    - Milvus (Vector database for claude-context semantic code search)
      - Ports: 19530 (Milvus API), 9001 (MinIO Console)

EXAMPLES:
    # Start services before using Claude Code
    ./dx/mcp-services.sh start

    # Check if services are running
    ./dx/mcp-services.sh status

    # View Milvus logs
    ./dx/mcp-services.sh logs

    # Stop services when done (saves resources)
    ./dx/mcp-services.sh stop

TROUBLESHOOTING:
    If services fail to start:
    1. Check Docker is running: docker info
    2. Check port conflicts: lsof -i :19530 -i :9001
    3. Check logs: ./dx/mcp-services.sh logs
    4. Try restart: ./dx/mcp-services.sh restart

    If Milvus connection fails:
    - Verify Milvus is healthy: docker ps | grep milvus
    - Check Milvus health endpoint: curl http://localhost:9091/healthz

RELATED:
    - MCP server setup: ./dx/setup-mcp-servers.sh
    - Documentation: dx/MCP_SERVERS.md

EOF
}

main() {
    local command="${1:-help}"

    case "$command" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            status_services
            ;;
        logs)
            logs_services
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

main "$@"

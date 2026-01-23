#!/bin/bash
# Toggle between LangSmith proxy (Langfuse) and direct LangSmith

set -e

MODE="${1:-}"

show_usage() {
    echo "Usage: $0 [proxy|direct|status]"
    echo ""
    echo "  proxy   - Route LangGraph traces to Langfuse via proxy"
    echo "  direct  - Route LangGraph traces directly to LangSmith cloud"
    echo "  status  - Show current configuration"
    echo ""
    echo "Examples:"
    echo "  $0 proxy    # Production mode (traces → Langfuse)"
    echo "  $0 direct   # Development mode (traces → LangSmith)"
    echo "  $0 status   # Check current mode"
}

check_status() {
    if grep -q "^LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002" .env 2>/dev/null; then
        echo "✅ PROXY MODE: Traces go to Langfuse via langsmith-proxy"
        echo "   LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002"
    elif grep -q "^LANGCHAIN_ENDPOINT=https://api.smith.langchain.com" .env 2>/dev/null; then
        echo "🔧 DIRECT MODE: Traces go directly to LangSmith cloud"
        echo "   LANGCHAIN_ENDPOINT=https://api.smith.langchain.com"
    elif grep -q "^#.*LANGCHAIN_ENDPOINT" .env 2>/dev/null || ! grep -q "LANGCHAIN_ENDPOINT" .env 2>/dev/null; then
        echo "🔧 DIRECT MODE (default): Traces go directly to LangSmith cloud"
        echo "   LANGCHAIN_ENDPOINT not set (uses LangSmith default)"
    else
        echo "❓ UNKNOWN MODE: Check .env file manually"
    fi
}

enable_proxy() {
    echo "📊 Enabling LangSmith proxy mode..."

    # Comment out any existing LANGCHAIN_ENDPOINT
    if grep -q "^LANGCHAIN_ENDPOINT=" .env 2>/dev/null; then
        sed -i.bak 's/^LANGCHAIN_ENDPOINT=/#LANGCHAIN_ENDPOINT=/' .env
    fi

    # Add proxy configuration
    if ! grep -q "^LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002" .env 2>/dev/null; then
        echo "" >> .env
        echo "# LangSmith Proxy (traces → Langfuse)" >> .env
        echo "LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002" >> .env
        echo "LANGCHAIN_API_KEY=dummy" >> .env
    fi

    echo "✅ Proxy mode enabled!"
    echo "   LangGraph traces will now go to Langfuse via proxy"
    echo ""
    echo "Restart services:"
    echo "   docker compose restart agent-service"
}

enable_direct() {
    echo "🔧 Enabling direct LangSmith mode..."

    # Comment out proxy endpoint
    if grep -q "^LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002" .env 2>/dev/null; then
        sed -i.bak 's/^LANGCHAIN_ENDPOINT=http/#LANGCHAIN_ENDPOINT=http/' .env
        sed -i.bak '/^LANGCHAIN_API_KEY=dummy/d' .env
    fi

    # Ensure real LangSmith endpoint is set
    if ! grep -q "^LANGCHAIN_ENDPOINT=https://api.smith.langchain.com" .env 2>/dev/null; then
        # Uncomment if exists
        if grep -q "^#.*LANGCHAIN_ENDPOINT=https://api.smith.langchain.com" .env 2>/dev/null; then
            sed -i.bak 's/^#\(LANGCHAIN_ENDPOINT=https\)/\1/' .env
        else
            echo "" >> .env
            echo "# Direct LangSmith (traces → LangSmith cloud)" >> .env
            echo "LANGCHAIN_ENDPOINT=https://api.smith.langchain.com" >> .env
        fi
    fi

    # Ensure LANGSMITH_API_KEY is set
    if ! grep -q "^LANGSMITH_API_KEY=" .env 2>/dev/null; then
        echo "⚠️  Warning: LANGSMITH_API_KEY not set in .env"
        echo "   Add your LangSmith API key to .env:"
        echo "   LANGSMITH_API_KEY=lsv2_pt_your-key"
    fi

    echo "✅ Direct mode enabled!"
    echo "   LangGraph traces will now go directly to LangSmith cloud"
    echo ""
    echo "Restart services:"
    echo "   docker compose restart agent-service"
}

case "$MODE" in
    proxy)
        enable_proxy
        ;;
    direct)
        enable_direct
        ;;
    status)
        check_status
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

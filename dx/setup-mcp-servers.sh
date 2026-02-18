#!/usr/bin/env bash
#
# MCP Server Setup Script for InsightMesh
# Sets up Model Context Protocol servers for enhanced AI code navigation
#
# Usage:
#   ./dx/setup-mcp-servers.sh
#
# What this installs:
#   - cclsp: Bridges Pyright LSP to Claude Code for semantic navigation
#   - claude-context: Semantic code search using Milvus vector database
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed"
        return 1
    fi
    log_success "$1 is installed"
    return 0
}

main() {
    log_info "Starting MCP server setup for InsightMesh..."
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."

    if ! check_command "node"; then
        log_error "Node.js is required. Install with: brew install node"
        exit 1
    fi

    if ! check_command "npm"; then
        log_error "npm is required (should come with Node.js)"
        exit 1
    fi

    if ! check_command "docker"; then
        log_error "Docker is required for claude-context (Milvus). Install with: brew install docker"
        exit 1
    fi

    if ! check_command "git"; then
        log_error "Git is required. Install with: brew install git"
        exit 1
    fi

    if ! check_command "pyright"; then
        log_warning "Pyright not found in PATH. Installing globally..."
        npm install -g pyright
        log_success "Pyright installed"
    fi

    if ! check_command "codeql"; then
        log_warning "CodeQL not found. Installing via Homebrew..."
        if brew install codeql; then
            log_success "CodeQL installed"
        else
            log_warning "Failed to install CodeQL. Install manually: brew install codeql"
        fi
    fi

    # Check for uv (recommended for Python package management)
    if ! check_command "uv"; then
        log_warning "uv not found. Installing uv for faster Python package management..."
        if curl -LsSf https://astral.sh/uv/install.sh | sh; then
            log_success "uv installed successfully"
            export PATH="$HOME/.cargo/bin:$PATH"
        else
            log_warning "Failed to install uv. Will fall back to pip for Python packages."
        fi
    fi

    echo

    # Install cclsp (Claude Code LSP - MCP language server bridge)
    log_info "Installing cclsp (MCP language server bridge)..."
    if npm install -g cclsp; then
        log_success "cclsp installed successfully"
    else
        log_error "Failed to install cclsp"
        exit 1
    fi

    echo

    # Install claude-context (Zilliz code search with Milvus)
    log_info "Installing claude-context MCP server..."
    if npm install -g @zilliz/claude-context-mcp; then
        log_success "claude-context installed successfully"
    else
        log_error "Failed to install claude-context"
        exit 1
    fi

    echo

    # Verify installation
    log_info "Verifying installation..."
    if command -v cclsp &> /dev/null; then
        log_success "cclsp is available in PATH"
    else
        log_warning "cclsp not found in PATH. You may need to add npm global bin to PATH:"
        echo "  export PATH=\"\$(npm config get prefix)/bin:\$PATH\""
        echo
    fi

    # Check and fix PATH for npm global packages
    NPM_PREFIX=$(npm config get prefix)
    if [[ ":$PATH:" != *":$NPM_PREFIX/bin:"* ]]; then
        log_warning "npm global bin not in PATH. Adding to your shell config..."

        # Detect shell
        if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
            SHELL_RC="$HOME/.zshrc"
        else
            SHELL_RC="$HOME/.bashrc"
        fi

        # Add to shell config if not already there
        if ! grep -q "npm config get prefix" "$SHELL_RC" 2>/dev/null; then
            echo "" >> "$SHELL_RC"
            echo "# Added by InsightMesh MCP setup" >> "$SHELL_RC"
            echo 'export PATH="$(npm config get prefix)/bin:$PATH"' >> "$SHELL_RC"
            log_success "Added npm global bin to $SHELL_RC"
        fi

        # Also export for current session
        export PATH="$NPM_PREFIX/bin:$PATH"
        log_success "Updated PATH for current session"
    fi

    if command -v claude-context &> /dev/null; then
        log_success "claude-context is available in PATH"
    else
        log_warning "claude-context still not found. You may need to restart your terminal."
    fi

    echo

    # Create MCP config directory if it doesn't exist
    MCP_CONFIG_DIR="$HOME/.config/claude-code"
    if [ ! -d "$MCP_CONFIG_DIR" ]; then
        log_info "Creating Claude Code config directory at $MCP_CONFIG_DIR"
        mkdir -p "$MCP_CONFIG_DIR"
    fi

    # Copy MCP configuration
    log_info "Installing MCP server configuration..."
    cp "$SCRIPT_DIR/mcp-config.json" "$MCP_CONFIG_DIR/mcp-config.json"
    log_success "MCP config installed to $MCP_CONFIG_DIR/mcp-config.json"

    echo

    # Summary
    log_success "MCP server setup complete!"
    echo
    echo "Next steps:"
    echo "  1. Start required services: ./dx/mcp-services.sh start"
    echo "  2. Restart Claude Code to load the new MCP servers"
    echo "  3. Read dx/MCP_SERVERS.md for usage guide"
    echo
    echo "Installed servers:"
    echo "  - cclsp (Pyright LSP → MCP bridge for semantic navigation)"
    echo "  - claude-context (Semantic code search with Milvus vector DB)"
    echo
    echo "Required services (managed by ./dx/mcp-services.sh):"
    echo "  - Milvus (vector database for claude-context)"
    echo
    echo "Configuration location:"
    echo "  $MCP_CONFIG_DIR/mcp-config.json"
}

main "$@"

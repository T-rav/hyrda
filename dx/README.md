# Developer Experience (DX) Tools

This directory contains tooling and configuration to enhance the developer experience when working with InsightMesh.

## Quick Start

```bash
# Set up AI code navigation (MCP servers)
./dx/setup-mcp-servers.sh

# Start required services (Milvus + CodeQL)
./dx/mcp-services.sh start

# Restart Claude Code to load the servers
```

**Note:** Don't confuse `./dx/mcp-services.sh` (manages MCP infrastructure) with `./claude.sh` in project root (launches Claude CLI).

---

## What's in this folder?

### MCP Servers (AI Code Navigation & Memory)

**Purpose:** Enable Claude Code to semantically understand your Python codebase and maintain long-term context.

**Files:**
- `setup-mcp-servers.sh` - One-command installation script for MCP servers
- `mcp-services.sh` - Service manager for required infrastructure (Milvus + CodeQL)
- `mcp-config.json` - MCP server configuration (copied to `~/.config/claude-code/`)
- `cclsp.json` - Language server configuration for Pyright
- `MCP_SERVERS.md` - Complete documentation on usage, troubleshooting, and examples
- `milvus/` - Milvus vector database configuration for claude-context
- `codeql-mcp/` - CodeQL MCP server (cloned during setup)

**Installed MCP Servers:**
1. **cclsp** - Semantic code navigation via Pyright LSP
2. **claude-context** - Long-term memory using Milvus vector database

**Quick reference:**
```bash
# Install MCP servers
./dx/setup-mcp-servers.sh

# Start required services (Milvus)
./dx/mcp-services.sh start

# Check service status
./dx/mcp-services.sh status

# Stop services when done
./dx/mcp-services.sh stop

# Usage examples (ask Claude):
# Code navigation:
# - "Show all implementations of VectorStore protocol"
# - "Trace Slack message flow from handler to LLM service"
# - "Find all callers of process_message across services"
#
# Long-term memory:
# - "Remember: InsightMesh uses Qdrant for production RAG"
# - "What have we discussed about microservices architecture?"
# - "Recall our conversation about security best practices"
```

**Read more:** [MCP_SERVERS.md](MCP_SERVERS.md)

---

### Milvus (Alternative Vector Database)

**Purpose:** Experimental setup for Milvus as an alternative to Qdrant.

**Location:** `dx/milvus/`

**Status:** Exploratory - production uses Qdrant

---

## Why a `dx/` folder?

**Philosophy:** Developer tooling should be:
1. **Self-contained** - All scripts in one place
2. **Documented** - README + detailed docs for each tool
3. **Optional** - Core app doesn't depend on these
4. **Automated** - One command to set up

**Not included here:**
- Production deployment configs (see `docker-compose.prod.yml`)
- CI/CD configs (see `.github/workflows/`)
- Application code (see `bot/`, `tasks/`, etc.)

---

## Tool Inventory

| Tool | Purpose | Status | Docs |
|------|---------|--------|------|
| **MCP Servers** | AI code navigation + code search + security analysis | ✅ Production | [MCP_SERVERS.md](MCP_SERVERS.md) |
| **mcp-services.sh** | Service manager for MCP infrastructure (Milvus + CodeQL) | ✅ Production | Built-in help: `./dx/mcp-services.sh help` |
| **Milvus** | Vector DB for claude-context code search | ✅ Production | `milvus/docker-compose.yml` |
| **CodeQL** | Security analysis and vulnerability detection | ✅ Production | [GitHub CodeQL](https://codeql.github.com/) |

---

## Adding New DX Tools

When adding new developer tooling:

1. **Create a setup script** (e.g., `setup-{tool}.sh`)
   - Make it idempotent (safe to run multiple times)
   - Check prerequisites before installing
   - Provide clear success/error messages

2. **Add configuration files** (if needed)
   - Example: `{tool}-config.json`
   - Document all options

3. **Write comprehensive docs** (e.g., `{TOOL}_GUIDE.md`)
   - Purpose and use cases
   - Installation instructions
   - Usage examples
   - Troubleshooting
   - When NOT to use it

4. **Update this README**
   - Add to tool inventory table
   - Add quick reference section

---

## Principles

**Keep it simple:**
- One command to install
- Clear documentation
- Fail loudly with helpful errors

**Keep it optional:**
- Core app works without these tools
- Developers can choose what to install
- No hidden dependencies

**Keep it maintained:**
- Document prerequisites
- Version dependencies
- Provide update instructions

---

## Related Documentation

- **Main project docs:** [../CLAUDE.md](../CLAUDE.md)
- **Development workflow:** [../Makefile](../Makefile)
- **Testing guide:** CLAUDE.md § Testing Framework
- **Security standards:** CLAUDE.md § Security Standards

---

**Last updated:** 2026-02-14

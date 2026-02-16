# MCP Servers for InsightMesh

**Model Context Protocol (MCP)** servers enhance AI code navigation by bridging language servers (LSPs) to Claude Code, enabling semantic understanding of your codebase.

## Quick Start

```bash
# Install MCP servers
./dx/setup-mcp-servers.sh

# Start required services
./dx/mcp-services.sh start

# Restart Claude Code to load the servers
# Verify by asking Claude: "Show me all implementations of VectorStore protocol"
```

## Installed MCP Servers

### 1. `cclsp` (Pyright LSP Bridge)

**Purpose:** Provides IDE-level semantic navigation for Python code.

**What it enables:**
- ✅ Go to definition across files
- ✅ Find all references (where is this function called?)
- ✅ Type information and inference
- ✅ Symbol search (find all classes matching pattern)
- ✅ Workspace symbols (cross-service navigation)
- ✅ Call hierarchy (trace execution flow)

**When to use:**
- "Show all callers of `process_message` across services"
- "Find definition of `RAGService.search`"
- "What implements the `EmbeddingProvider` protocol?"
- "Trace Slack event flow through handlers"
- "Show all files that import `SlackService`"

**Example queries:**
```
Claude, using the language server:
- Show me all implementations of the VectorStore protocol
- Find every place that calls embedding_service.embed()
- What's the type signature of process_slack_event?
- Show the call hierarchy for handle_message
- List all classes in the bot/services directory
```

**Technical details:**
- **Language Server:** Pyright (already in your dev stack)
- **Bridge:** `cclsp` (Claude Code LSP)
- **Config:** `~/.config/claude-code/mcp-config.json` + `dx/cclsp.json`
- **Scope:** All Python files in InsightMesh

**Benefits for InsightMesh:**
- Navigate 5 microservices (bot, agent-service, control-plane, tasks, rag-service) semantically
- Your codebase has strict type annotations (CLAUDE.md requirement) → high accuracy
- Cross-service tracing (bot → control-plane → agent-service)
- Find security patterns (all places using encryption, OAuth, secrets)

---

### 2. `claude-context` (Long-term Memory with Milvus)

**Purpose:** Provides long-term memory and context management for Claude using a vector database.

**What it enables:**
- ✅ Store conversation context persistently
- ✅ Retrieve relevant past conversations
- ✅ Semantic search over conversation history
- ✅ Project-specific memory (remembers decisions, patterns, architecture)
- ✅ Cross-session knowledge retention

**When to use:**
- "Remember that we use OAuth2 for Google Drive authentication"
- "What architectural decisions have we made about the RAG service?"
- "What did we discuss about the Milvus vs Qdrant decision?"
- "Recall our conversation about security best practices"
- "What patterns have we established for error handling?"

**Example queries:**
```
# Store context
Claude, remember this: InsightMesh uses Qdrant in production and Milvus for MCP context storage

# Retrieve context
What do you remember about our vector database choices?

# Semantic search
What have we discussed about microservices architecture?

# Project decisions
What testing standards have we established?
```

**Technical details:**
- **Vector Database:** Milvus (dedicated instance for MCP)
- **MCP Server:** `@cyanheads/claude-context`
- **Storage:** Persistent volumes in `dx/milvus/volumes/`
- **Ports:** 19530 (Milvus API), 9001 (MinIO Console)

**Setup requirements:**
```bash
# Start Milvus before using claude-context
./dx/mcp-services.sh start

# Verify Milvus is running
./dx/mcp-services.sh status

# View logs if issues
./dx/mcp-services.sh logs

# Stop when done (saves resources)
./dx/mcp-services.sh stop
```

**Benefits for InsightMesh:**
- Remember architectural decisions across sessions
- Recall past discussions about trade-offs
- Build up project-specific knowledge over time
- Avoid repeating context in every conversation
- Persistent memory of coding patterns and preferences

**Storage location:**
- Context database: `dx/milvus/volumes/milvus/`
- Configuration: `~/.config/claude-code/mcp-config.json`

**Resource usage:**
- Milvus containers: ~500MB RAM
- Disk: Growing (conversation history)
- Start/stop as needed to manage resources

---

### 3. `codeql` (Security Analysis with CodeQL)

**Purpose:** Deep static analysis for security vulnerabilities and code quality issues.

**What it enables:**
- ✅ Detect security vulnerabilities (SQL injection, XSS, etc.)
- ✅ Find code quality issues
- ✅ Trace data flows across functions
- ✅ Build and query call graphs
- ✅ Custom security queries
- ✅ Compliance checking (OWASP, CWE)

**When to use:**
- "Find all SQL queries that don't use parameterization"
- "Detect potential security vulnerabilities in authentication code"
- "Show me all places where user input reaches sensitive sinks"
- "Find hardcoded secrets or credentials"
- "Trace data flow from HTTP request to database query"
- "Check for OWASP Top 10 vulnerabilities"

**Example queries:**
```
# Security analysis
Find all potential SQL injection vulnerabilities in the codebase

# Data flow tracing
Trace user input from Slack events to database operations

# Code quality
Find all functions that are never called

# Compliance
Check for CWE-based vulnerabilities in authentication code
```

**Technical details:**
- **Static Analysis Engine:** CodeQL (by GitHub Security Lab)
- **MCP Server:** `codeql-mcp` by JordyZomer
- **Database:** Requires CodeQL database creation first
- **Endpoint:** http://localhost:8000/sse

**Setup requirements:**
```bash
# CodeQL is installed during setup
# Check installation
codeql --version

# Create CodeQL database for InsightMesh
cd /Users/travisf/Documents/projects/insightmesh
codeql database create \
  --language=python \
  --source-root=. \
  insightmesh-codeql-db

# Start CodeQL MCP server (managed by mcp-services.sh)
./dx/mcp-services.sh start

# Now Claude can query CodeQL
```

**Benefits for InsightMesh:**
- Find security vulnerabilities across 5 microservices
- Trace data flows from Slack input to database
- Ensure OAuth/secrets handling is secure
- Validate input sanitization
- Compliance with security policies (CLAUDE.md § Security Standards)

**CodeQL database locations:**
- Recommended: `insightmesh-codeql-db` (project root, in .gitignore)
- Alternative: Separate directory per service

**Query examples for InsightMesh:**
- "Find all places where Slack user input is used in SQL queries"
- "Show authentication flow from bot to agent-service"
- "Detect potential secret leaks in environment variable usage"
- "Find all API endpoints that don't validate input"

---

## Architecture

```
                         ┌────────────────────────────────┐
                         │   Claude Code (AI Agent)       │
                         └───┬──────────┬──────────┬──────┘
                             │          │          │
        ┌────────────────────┘          │          └──────────────────┐
        │ MCP                            │ MCP                         │ MCP
        ▼                                ▼                             ▼
┌──────────────────┐       ┌─────────────────────┐       ┌────────────────────┐
│      cclsp       │       │  claude-context     │       │  codeql-mcp        │
│ (Code Nav)       │       │  (Code Search)      │       │  (Security)        │
└────────┬─────────┘       └──────────┬──────────┘       └─────────┬──────────┘
         │ LSP                         │                             │ JSON-RPC
         ▼                             ▼                             ▼
┌──────────────────┐       ┌─────────────────────┐       ┌────────────────────┐
│  Pyright LSP     │       │  Milvus Vector DB   │       │  CodeQL Engine     │
│  • Types         │       │  • Embeddings       │       │  • Static analysis │
│  • References    │       │  • Semantic search  │       │  • Data flow       │
│  • Symbols       │       │  • Code indexing    │       │  • Vulnerability   │
└────────┬─────────┘       └─────────────────────┘       └─────────┬──────────┘
         │                                                           │
         └───────────────────────────┬───────────────────────────────┘
                                     ▼
                ┌────────────────────────────────────────────────────┐
                │        InsightMesh Python Codebase                 │
                │  bot/ agent-service/ control-plane/ tasks/         │
                │  rag-service/                                      │
                └────────────────────────────────────────────────────┘
```

**How cclsp works:**
1. Claude asks: "Show all callers of `process_message`"
2. cclsp MCP server translates to LSP request: `textDocument/references`
3. Pyright analyzes code and returns semantic results
4. cclsp formats results for Claude via MCP protocol
5. Claude presents findings to you

**How claude-context works:**
1. Claude indexes codebase: "Index this codebase for semantic search"
2. MCP server chunks code and creates embeddings
3. Stores code embeddings in Milvus vector database
4. Later, Claude searches: "Find authentication code"
5. MCP server performs semantic search in Milvus
6. Returns relevant code snippets to Claude

**How codeql works:**
1. You create CodeQL database: `codeql database create --language=python db`
2. Claude asks: "Find SQL injection vulnerabilities"
3. MCP server translates to CodeQL query
4. CodeQL analyzes code and traces data flows
5. Returns findings with file locations and severity
6. Claude presents security issues with context

---

## Why These Servers?

### Chosen: `cclsp` (Pyright via Claude Code LSP)

**Rationale:**
- ✅ **Already in your stack:** You use Pyright for type checking (`make lint`)
- ✅ **Type-annotated codebase:** Required by CLAUDE.md → high LSP accuracy
- ✅ **Microservices architecture:** Critical for cross-service navigation
- ✅ **Zero setup cost:** Leverages existing Pyright configuration
- ✅ **Mature and stable:** Pyright by Microsoft + cclsp by ktnyt
- ✅ **Active development:** cclsp actively maintained with good documentation

**Alternative considered:** Sourcegraph
- ❌ Only valuable for multi-repo codebases
- ❌ InsightMesh is a monorepo

**Alternative considered:** Semgrep MCP
- ⏳ Useful for pattern-based queries (e.g., "find all SQL queries")
- ⏳ Future addition if pattern tracing becomes a bottleneck
- ⏳ Your security scanning already uses Bandit

---

### Chosen: `claude-context` (Long-term Memory)

**Rationale:**
- ✅ **Project complexity:** 5 microservices with many architectural decisions
- ✅ **Persistent knowledge:** Remember decisions, patterns, and trade-offs across sessions
- ✅ **Reduce repetition:** Stop re-explaining context every conversation
- ✅ **Team knowledge base:** Build up institutional knowledge over time
- ✅ **Already have Milvus:** Exploring as Qdrant alternative, reuse for MCP

**Why Milvus over other vector DBs for MCP:**
- ✅ **Separate from production:** Production uses Qdrant, MCP uses Milvus (isolation)
- ✅ **Already configured:** `dx/milvus/` setup ready to use
- ✅ **Performance:** Fast similarity search for context retrieval
- ✅ **Persistence:** Conversation history survives restarts

**Alternative considered:** File-based context
- ❌ No semantic search
- ❌ Manual organization required
- ❌ Doesn't scale well

**Alternative considered:** Qdrant (reuse production instance)
- ❌ Mix MCP context with production RAG data
- ❌ Production instance not always running locally
- ✅ Prefer isolation

---

### Chosen: `codeql` (Security Analysis)

**Rationale:**
- ✅ **Security-first codebase:** CLAUDE.md mandates comprehensive security (Bandit, pre-commit hooks)
- ✅ **Deep analysis:** CodeQL traces data flows, not just pattern matching (vs Bandit)
- ✅ **Multi-service architecture:** Security issues can span services (Slack → bot → database)
- ✅ **Compliance:** Required for 8th Light Host Hardening Policy (CLAUDE.md)
- ✅ **Custom queries:** Can write InsightMesh-specific security rules
- ✅ **MCP integration:** AI can automatically find and fix vulnerabilities

**Why CodeQL + Bandit (not either/or):**
- ✅ **CodeQL:** Deep static analysis, data flow tracking, custom queries
- ✅ **Bandit:** Fast, pre-commit hook integration, catches common issues
- ✅ **Complementary:** Bandit in CI, CodeQL via MCP for deep analysis on demand

**Alternative considered:** SonarQube
- ❌ Heavy infrastructure (requires server)
- ❌ No MCP integration
- ❌ CodeQL more specialized for security

**Alternative considered:** Semgrep only
- ⚠️ Pattern-based (can't trace data flows like CodeQL)
- ⚠️ Less comprehensive security coverage
- ✅ Could add as supplementary tool later

---

## Configuration

**Location:** `~/.config/claude-code/mcp-config.json`

**MCP Config (`~/.config/claude-code/mcp-config.json`):**
```json
{
  "mcpServers": {
    "cclsp": {
      "command": "cclsp",
      "env": {
        "CCLSP_CONFIG_PATH": "/Users/travisf/Documents/projects/insightmesh/dx/cclsp.json"
      }
    },
    "claude-context": {
      "command": "npx",
      "args": ["-y", "@cyanheads/claude-context"],
      "env": {
        "MILVUS_HOST": "localhost",
        "MILVUS_PORT": "19530",
        "CLAUDE_CONTEXT_DB": "insightmesh_context"
      }
    }
  }
}
```

**cclsp Language Server Config (`dx/cclsp.json`):**
```json
{
  "servers": [
    {
      "extensions": ["py", "pyi"],
      "command": ["pyright-langserver", "--stdio"],
      "rootDir": "/Users/travisf/Documents/projects/insightmesh",
      "initializationOptions": {
        "settings": {
          "python": {
            "analysis": {
              "typeCheckingMode": "strict",
              "autoSearchPaths": true,
              "useLibraryCodeForTypes": true
            }
          }
        }
      }
    }
  ]
}
```

**Customization:**

To adjust Pyright strictness, create `pyrightconfig.json` in project root:
```json
{
  "typeCheckingMode": "strict",
  "reportMissingImports": true,
  "reportMissingTypeStubs": false,
  "include": [
    "bot",
    "agent-service",
    "control-plane",
    "tasks",
    "rag-service"
  ],
  "exclude": [
    "**/node_modules",
    "**/__pycache__",
    "**/venv"
  ]
}
```

---

## Troubleshooting

### MCP server not loading

**Symptoms:** Claude can't use semantic navigation

**Fix:**
```bash
# Check if cclsp is in PATH
which cclsp

# If not found, add npm global bin to PATH
export PATH="$(npm config get prefix)/bin:$PATH"

# Add to ~/.zshrc or ~/.bashrc to persist
echo 'export PATH="$(npm config get prefix)/bin:$PATH"' >> ~/.zshrc

# Verify cclsp can find language servers
cclsp --version

# Restart Claude Code
```

### Pyright errors in MCP logs

**Symptoms:** MCP server starts but returns errors

**Fix:**
```bash
# Verify Pyright works standalone
cd /Users/travisf/Documents/projects/insightmesh
pyright bot/services/

# Check Python environment
which python  # Should be venv or system Python

# Ensure dependencies installed
make install
```

### Slow responses

**Symptoms:** Semantic queries take >5 seconds

**Possible causes:**
- Large workspace (normal for 5 microservices)
- First query triggers indexing (one-time cost)

**Optimization:**
```bash
# Exclude unnecessary directories from Pyright analysis
# Add to pyrightconfig.json:
{
  "exclude": [
    "**/node_modules",
    "**/__pycache__",
    "**/venv",
    "**/migrations",
    "**/tests"  // Optional: exclude if tests slow down indexing
  ]
}
```

### Check MCP server status

```bash
# View Claude Code logs (location varies by OS)
# macOS:
tail -f ~/Library/Logs/Claude\ Code/main.log

# Look for lines containing "cclsp" or "claude-context"
```

---

### claude-context: Milvus not running

**Symptoms:** Claude can't store/retrieve context, "connection refused" errors

**Fix:**
```bash
# Start Milvus services
./dx/mcp-services.sh start

# Verify Milvus is healthy
./dx/mcp-services.sh status

# Check specific container
docker ps | grep milvus

# Test Milvus health endpoint
curl http://localhost:9091/healthz
```

**Common causes:**
- Docker not running: Start Docker Desktop
- Port conflicts: Check `lsof -i :19530 -i :9001`
- Containers failed: Check `./dx/mcp-services.sh logs`

---

### claude-context: Connection timeout

**Symptoms:** Claude hangs when trying to use context features

**Fix:**
```bash
# Restart Milvus services
./dx/mcp-services.sh restart

# Check Milvus logs
./dx/mcp-services.sh logs

# Verify network connectivity
docker network ls | grep milvus
docker network inspect milvus

# Ensure containers are on correct network
docker inspect milvus-standalone | grep NetworkMode
```

---

### claude-context: Context not persisting

**Symptoms:** Context stored but not retrieved after restart

**Fix:**
```bash
# Check volume mounts
ls -la dx/milvus/volumes/milvus/

# Verify Milvus data directory has content
du -sh dx/milvus/volumes/milvus/

# Check container logs for errors
docker logs milvus-standalone

# If corrupted, recreate (WARNING: loses all context)
./dx/mcp-services.sh stop
rm -rf dx/milvus/volumes/
./dx/mcp-services.sh start
```

---

### Check all MCP services

```bash
# Quick status check
./dx/mcp-services.sh status

# Check MCP server processes
ps aux | grep -E "cclsp|claude-context"

# View all logs
./dx/mcp-services.sh logs
```

---

### CodeQL: Database not found

**Symptoms:** Claude can't run CodeQL queries, "database not found" errors

**Fix:**
```bash
# Create CodeQL database for Python
cd /Users/travisf/Documents/projects/insightmesh
codeql database create \
  --language=python \
  --source-root=. \
  insightmesh-codeql-db

# Verify database
codeql database info insightmesh-codeql-db

# Tell Claude about the database location
# "Use the CodeQL database at insightmesh-codeql-db to find vulnerabilities"
```

---

### CodeQL: MCP server not responding

**Symptoms:** CodeQL queries timeout or fail

**Fix:**
```bash
# Check if server is running
./dx/mcp-services.sh status

# View server logs
./dx/mcp-services.sh logs codeql

# Restart server
./dx/mcp-services.sh restart

# Test endpoint manually
curl http://localhost:8000/sse
```

---

### CodeQL: Slow query execution

**Symptoms:** CodeQL queries take >30 seconds

**Possible causes:**
- Large codebase (normal for complex queries)
- Database needs upgrading
- Resource constraints

**Optimization:**
```bash
# Upgrade CodeQL database (after CodeQL CLI updates)
codeql database upgrade insightmesh-codeql-db

# Create service-specific databases for faster queries
cd bot && codeql database create --language=python bot-codeql-db
cd tasks && codeql database create --language=python tasks-codeql-db

# Use specific database in queries
# Tell Claude: "Use bot-codeql-db to find auth vulnerabilities"
```

---

## Usage Examples

### 1. Find all implementations of a protocol

**Query:**
```
Show me all classes that implement the VectorStore protocol
```

**What Claude does:**
1. Uses `cclsp` to find `VectorStore` definition in `bot/services/protocols/`
2. Searches workspace for all implementations via Pyright
3. Returns:
   - `bot/services/vector_stores/qdrant.py:QdrantVectorStore`
   - `bot/tests/utils/mocks/mock_vector_store_factory.py:MockVectorStore`

### 2. Trace a service method across microservices

**Query:**
```
Trace the call flow when a Slack message arrives, from handler to LLM service
```

**What Claude does:**
1. Finds `handle_message` in `bot/handlers/message_handlers.py`
2. Uses call hierarchy to trace through:
   - `bot/handlers/message_handlers.py:handle_message`
   - `bot/services/slack_service.py:process_message`
   - `bot/services/llm_service.py:generate_response`
3. Shows full execution path with file locations

### 3. Find all security-sensitive operations

**Query:**
```
Show me all places where we handle OAuth credentials or encryption keys
```

**What Claude does:**
1. Searches for symbols related to `OAuth`, `encryption`, `secret`
2. Uses references to find usage sites
3. Returns:
   - `tasks/models/oauth_credential.py:OAuthCredential`
   - `tasks/services/encryption_service.py:encrypt_credential`
   - All call sites across services

### 4. Understand type information

**Query:**
```
What's the return type of RAGService.search() and where is it defined?
```

**What Claude does:**
1. Finds `RAGService.search` definition
2. Resolves type annotations
3. Returns:
   - Return type: `list[RetrievalResult]`
   - Definition: `bot/services/rag_service.py:145`
   - Type definition: `bot/models/retrieval.py:RetrievalResult`

### 5. Find security vulnerabilities with CodeQL

**Query:**
```
Find all SQL queries that might be vulnerable to SQL injection
```

**What Claude does:**
1. Uses `codeql` MCP server with insightmesh-codeql-db
2. Runs taint analysis from user input to SQL execution
3. Returns:
   - Vulnerable code locations with file:line
   - Data flow path (source → sink)
   - Severity and CWE classification
   - Recommended fixes

**Example output:**
```
Found 2 potential SQL injection vulnerabilities:

1. bot/services/database.py:45
   - User input from Slack message flows to execute_query()
   - CWE-89: SQL Injection
   - Severity: High
   - Fix: Use parameterized queries

2. tasks/services/metric_client.py:102
   - Query string concatenation with user input
   - CWE-89: SQL Injection
   - Severity: Medium
   - Fix: Use ORM query builder
```

### 6. Trace data flows across microservices

**Query:**
```
Trace how Slack user input flows through the bot to database operations
```

**What Claude does:**
1. Uses CodeQL to build call graph
2. Traces data flow from Slack event handlers
3. Follows through service calls
4. Returns complete flow with security checkpoints

**Example trace:**
```
Data flow analysis:
1. bot/handlers/message_handlers.py:handle_message (source: Slack event)
2. bot/handlers/message_handlers.py:process_user_message
3. bot/services/slack_service.py:validate_input ✓ (sanitized)
4. bot/services/llm_service.py:generate_response
5. bot/services/rag_service.py:search (sink: vector DB query)

Security: Input is validated at step 3, no vulnerabilities detected.
```

### 7. Find hardcoded secrets

**Query:**
```
Find all hardcoded API keys, passwords, or tokens in the codebase
```

**What Claude does:**
1. Uses CodeQL secret detection queries
2. Searches for string patterns matching credentials
3. Checks if values come from environment variables (good) or hardcoded (bad)
4. Returns findings with remediation steps

---

## Performance Impact

### cclsp (Pyright)
**First query (cold start):**
- Pyright indexes workspace: ~3-5 seconds (one-time)
- Subsequent queries: <500ms

**Memory usage:**
- Pyright process: ~100-200MB

### claude-context (Milvus)
**Indexing (one-time):**
- Initial codebase indexing: ~1-2 minutes for InsightMesh (~20k LOC)
- Subsequent searches: <1 second

**Memory usage:**
- Milvus containers: ~500MB RAM
- Disk: ~50-100MB for code embeddings

### codeql (CodeQL Engine)
**Database creation (one-time):**
- Full codebase analysis: ~5-10 minutes for InsightMesh
- Database size: ~200-500MB

**Query execution:**
- Simple queries: 1-5 seconds
- Complex data flow analysis: 10-30 seconds

**Memory usage:**
- CodeQL MCP server: ~50-100MB
- CodeQL engine during queries: ~500MB-1GB

### Overall System Impact
- Total RAM: ~1-2GB (all services running)
- Total disk: ~1GB (databases + volumes)
- Fine for development machines (8GB+ RAM recommended)

**When to disable:**
- Low-memory environments (<4GB RAM)
- Use mcp-services.sh stop when not coding to save resources

---

## Future MCP Servers to Consider

### 1. Semgrep MCP (Pattern-based search)

**When to add:** If you frequently need to find code patterns:
- "Find all SQL queries that don't use parameterization"
- "Show all API endpoints that return user data"
- "Find places where we call external APIs without timeout"

**Setup:**
```bash
pip install semgrep
# Configure Semgrep MCP server (TBD - not yet released)
```

### 2. CodeQL (Deep static analysis)

**When to add:** If you need advanced security queries:
- Data flow analysis (taint tracking)
- Complex call graphs across multiple hops
- Custom security vulnerability patterns

**Setup:**
```bash
brew install codeql
codeql database create --language=python insightmesh-db
# Configure CodeQL MCP server (custom bridge needed)
```

**Note:** Your current security tooling (Bandit + Ruff + Pyright) likely covers 95% of needs.

### 3. GitHub Copilot Chat (Experimental)

**When to add:** If you want inline code suggestions in Claude Code
- Auto-complete based on context
- Code generation with project patterns

**Status:** Experimental integration, not stable yet

---

## Maintenance

### Update MCP servers

```bash
# Update mcp-language-server
npm update -g @isaacphi/mcp-language-server

# Update Pyright (optional, already managed by package.json)
npm update -g pyright

# Restart Claude Code after updates
```

### Verify health

```bash
# Test Pyright standalone
pyright --version
pyright bot/services/ --outputjson

# Test MCP server manually (advanced)
echo '{"method":"initialize"}' | mcp-language-server --stdio
```

---

## Documentation & Resources

**Model Context Protocol:**
- Specification: [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- Official SDK: [@modelcontextprotocol/sdk](https://www.npmjs.com/package/@modelcontextprotocol/sdk)
- Claude Code MCP guide: [Claude Docs](https://claude.ai/docs/mcp)

**cclsp (Language Server Bridge):**
- GitHub: [ktnyt/cclsp](https://github.com/ktnyt/cclsp)
- NPM: [cclsp](https://www.npmjs.com/package/cclsp)
- Documentation: [Getting Started](https://deepwiki.com/ktnyt/cclsp/1.1-getting-started)

**Pyright (Python Language Server):**
- GitHub: [microsoft/pyright](https://github.com/microsoft/pyright)
- Configuration: [Pyright Configuration](https://github.com/microsoft/pyright/blob/main/docs/configuration.md)

**claude-context (Code Search):**
- GitHub: [zilliztech/claude-context](https://github.com/zilliztech/claude-context)
- NPM: [@zilliz/claude-context-mcp](https://www.npmjs.com/package/@zilliz/claude-context-mcp)
- Milvus: [Milvus Documentation](https://milvus.io/docs)

**CodeQL (Security Analysis):**
- GitHub: [github/codeql](https://github.com/github/codeql)
- Documentation: [CodeQL Docs](https://codeql.github.com/docs/)
- MCP Server: [JordyZomer/codeql-mcp](https://github.com/JordyZomer/codeql-mcp)
- Query Library: [CodeQL Query Help](https://codeql.github.com/codeql-query-help/)

---

## Questions?

**"Should I use this or just grep?"**
- Use MCP for semantic queries (definitions, references, types)
- Use grep for text pattern matching (log messages, comments)

**"Will this slow down Claude?"**
- First query: 3-5 second indexing (one-time)
- Subsequent: <500ms overhead
- Worth it for accurate cross-service navigation

**"Can I disable it?"**
- Yes, remove from `~/.config/claude-code/mcp-config.json`
- Or set `"autoStart": false` for specific server

**"Does this send code to external services?"**
- No, everything runs locally
- Pyright analyzes on your machine
- MCP bridge is local process

---

**Last updated:** 2026-02-14
**Maintained by:** InsightMesh Dev Team
**Related docs:** `CLAUDE.md`, `Makefile` (quality commands)

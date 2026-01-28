# LangSmith to Langfuse Proxy

## Overview

The LangSmith proxy allows LangGraph agents to send traces to Langfuse instead of LangSmith cloud in production, while preserving the ability to use LangSmith for local development.

## Problem Solved

- **Production**: LangGraph agents have built-in LangSmith tracing, but we want traces in Langfuse
- **Local Dev**: LangSmith's UI is great for debugging, but we don't want to pay for cloud tracing in production
- **Unified Observability**: Keep all traces (bot + agents) in Langfuse

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Production (Embedded LangGraph Agents)                      │
│                                                               │
│  LangGraph Agent → LangSmith SDK → Proxy → Langfuse         │
│                                        ↓                      │
│                            (converts trace format)           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Local Development                                            │
│                                                               │
│  LangGraph Agent → LangSmith SDK → LangSmith Cloud          │
│                                        ↓                      │
│                            (use LangSmith UI for debugging)  │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Enable Proxy Mode (Production)

```bash
# Use helper script
./scripts/toggle-langsmith-proxy.sh proxy

# Or manually edit .env
LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002
LANGCHAIN_API_KEY=dummy  # Proxy doesn't validate keys

# Restart agent service
docker compose restart agent-service
```

### 2. Enable Direct Mode (Local Dev)

```bash
# Use helper script
./scripts/toggle-langsmith-proxy.sh direct

# Or manually edit .env
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<your-langsmith-api-key>

# Restart agent service
docker compose restart agent-service
```

### 3. Check Current Mode

```bash
./scripts/toggle-langsmith-proxy.sh status
```

## Docker Compose

The proxy is automatically configured in `docker-compose.yml`:

```yaml
langsmith-proxy:
  build: ./langsmith-proxy
  ports:
    - "8002:8002"
  environment:
    - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
    - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
    - LANGFUSE_HOST=${LANGFUSE_HOST}
```

Start it with:

```bash
docker compose up -d langsmith-proxy
```

## Translation: LangSmith → Langfuse

**Yes, the proxy translates trace formats!**

The proxy converts LangSmith's trace format to Langfuse's format in real-time:

```python
# LangSmith format (what agents send)
{
  "id": "run-123",
  "name": "agent_executor",
  "run_type": "chain",
  "inputs": {"query": "..."},
  "outputs": {"result": "..."},
  "parent_run_id": null,
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T00:00:05Z"
}

# ↓ Proxy converts to ↓

# Langfuse format (what gets stored)
langfuse.trace(
  id="run-123",
  name="agent_executor",
  input={"query": "..."},
  output={"result": "..."},
  metadata={"run_type": "chain"}
)
```

## Security

The proxy requires API key authentication to prevent unauthorized access.

### API Key Setup

```bash
# Generate a secure key
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: abc123def456...

# Add to .env
PROXY_API_KEY=abc123def456...
LANGCHAIN_API_KEY=${PROXY_API_KEY}  # Agent must use same key
```

### How Authentication Works

1. Agent sends trace with `Authorization: Bearer <key>` header
2. Proxy validates key matches `PROXY_API_KEY`
3. If valid → Forward to Langfuse
4. If invalid → Return `401 Unauthorized`

**Note:** If `PROXY_API_KEY` is not set, the proxy generates a temporary random key on startup and logs it. For production, always set it explicitly in `.env`.

## How It Works

### Trace Conversion

| LangSmith Format | Langfuse Format | When |
|------------------|-----------------|------|
| Root run | Trace | Top-level agent execution |
| Child run (llm) | Generation | LLM completions |
| Child run (chain) | Span | Agent chains/tools |
| Child run (tool) | Span | Tool invocations |
| Child run (retriever) | Span | RAG retrievals |

### Example Trace Flow

```python
# LangGraph agent executes
agent.invoke({"input": "analyze this company"})

# LangSmith SDK sends:
POST /runs
{
  "id": "run-123",
  "name": "agent_executor",
  "run_type": "chain",
  "inputs": {...}
}

# Proxy converts and forwards to Langfuse:
langfuse.trace(
  id="run-123",
  name="agent_executor",
  input={...}
)

# Child runs become spans:
POST /runs
{
  "id": "run-456",
  "parent_run_id": "run-123",
  "name": "llm_call",
  "run_type": "llm"
}

# → Becomes Langfuse generation:
trace.generation(
  id="run-456",
  name="llm_call",
  ...
)
```

## Environment Variables

### Proxy Configuration (`.env`)

```bash
# Option 1: Use proxy (production)
LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002
LANGCHAIN_API_KEY=dummy

# Option 2: Direct LangSmith (local dev)
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=<your-langsmith-api-key>

# Langfuse credentials (used by proxy)
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Proxy Service Configuration

Set these for the proxy container:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_DEBUG=false
PORT=8002
```

## API Endpoints

### LangSmith Compatible

- `POST /runs` - Create new run (trace/span/generation)
- `PATCH /runs/{run_id}` - Update run (completion, errors, outputs)
- `POST /runs/batch` - Batch create/update runs

### Proxy Specific

- `GET /health` - Health check and Langfuse status
- `GET /info` - Proxy metrics and run count

### Testing

```bash
# Check proxy health
curl http://localhost:8002/health
# Output: {"status":"healthy","langfuse_available":true}

# Check proxy info
curl http://localhost:8002/info
# Output: {"service":"LangSmith to Langfuse Proxy","version":"1.0.0",...}

# View proxy logs
docker logs -f insightmesh-langsmith-proxy
```

## Monitoring

### Proxy Logs

The proxy logs all trace activity with emojis for easy parsing:

```
📊 Created Langfuse trace: agent_executor (run-abc123)
📍 Created Langfuse span: web_search_tool (run-def456)
🤖 Created Langfuse generation: gpt-4-completion (run-ghi789)
✅ Completed Langfuse trace: agent_executor (run-abc123)
❌ Error in Langfuse run: Connection timeout
```

### Langfuse Dashboard

All traces appear in Langfuse with proper hierarchy:

```
Trace: agent_executor (run-abc123)
├── Span: web_search_tool (run-def456)
├── Generation: gpt-4-completion (run-ghi789)
│   └── Input: "search for company info"
│   └── Output: "Found 5 results"
└── Span: analysis_chain (run-jkl012)
```

## Troubleshooting

### Issue: Traces not appearing in Langfuse

**Check proxy logs:**
```bash
docker logs insightmesh-langsmith-proxy
```

**Verify Langfuse credentials:**
```bash
curl http://localhost:8002/health
# Should show: "langfuse_available": true
```

**Ensure agent points to proxy:**
```bash
docker compose exec agent-service env | grep LANGCHAIN_ENDPOINT
# Should show: http://langsmith-proxy:8002
```

### Issue: Agent still using LangSmith cloud

**Restart agent service after env change:**
```bash
docker compose restart agent-service
```

**Check network connectivity:**
```bash
docker compose exec agent-service ping langsmith-proxy
```

### Issue: Proxy container not starting

**Check Langfuse credentials:**
```bash
docker compose exec langsmith-proxy env | grep LANGFUSE
```

**Check proxy logs for errors:**
```bash
docker compose logs langsmith-proxy
```

## Benefits

1. **💰 Cost Savings**: No LangSmith cloud usage in production
2. **📊 Unified Observability**: All traces in one place (Langfuse)
3. **🛠️ Dev Flexibility**: Use LangSmith UI for local debugging
4. **🔌 Zero Code Changes**: Just environment variables
5. **🔍 Transparent**: Agents don't know they're using a proxy

## Limitations

- Proxy stores run ID mappings in memory (resets on restart)
- No LangSmith-specific features (datasets, evaluations, feedback)
- One-way sync only (Langfuse → LangSmith not supported)
- Proxy must be running before agents start

## Development Workflow

### Local Development

```bash
# 1. Use real LangSmith for debugging
./scripts/toggle-langsmith-proxy.sh direct

# 2. Set your LangSmith API key in .env
LANGSMITH_API_KEY=<your-langsmith-api-key>

# 3. Restart services
docker compose restart agent-service

# 4. Run agents - traces go to LangSmith cloud
# 5. View traces at https://smith.langchain.com
```

### Production Deployment

```bash
# 1. Generate and set proxy API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Add to .env: PROXY_API_KEY=your-generated-key

# 2. Enable proxy mode (auto-generates key if not set)
./scripts/toggle-langsmith-proxy.sh proxy

# 3. Ensure Langfuse credentials are set
grep LANGFUSE .env

# 4. Start proxy
docker compose up -d langsmith-proxy

# 5. Restart agents
docker compose restart agent-service

# 6. View traces in Langfuse dashboard
```

## Files

- `langsmith-proxy/app.py` - Proxy FastAPI application
- `langsmith-proxy/Dockerfile` - Proxy container definition
- `langsmith-proxy/README.md` - Detailed proxy documentation
- `scripts/toggle-langsmith-proxy.sh` - Helper script to switch modes
- `docker-compose.yml` - Proxy service definition

## See Also

- [Langfuse Documentation](https://langfuse.com/docs)
- [LangSmith Documentation](https://docs.smith.langchain.com)
- [LangGraph Tracing](https://langchain-ai.github.io/langgraph/how-tos/tracing/)

# LangSmith to Langfuse Proxy

Intercepts LangSmith tracing calls from LangGraph agents and forwards them to Langfuse.

## Purpose

- **Production/Embedded**: LangGraph agents send traces to Langfuse (not LangSmith cloud)
- **Local Development**: Use real LangSmith for debugging (bypass proxy)
- **Unified Tracing**: Keep all traces in Langfuse regardless of deployment mode

## Architecture

```
LangGraph Agent → LangSmith SDK → Proxy → Langfuse
                                     ↓
                          (converts format)
```

## Configuration

### Production (Use Proxy)

```bash
# Point LangGraph to proxy
LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002
LANGCHAIN_API_KEY=dummy  # Proxy doesn't validate

# Langfuse credentials (proxy uses these)
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Local Development (Bypass Proxy)

```bash
# Point LangGraph to real LangSmith
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=lsv2_pt_xxx  # Your real LangSmith key

# Or unset to use defaults
unset LANGCHAIN_ENDPOINT
```

## Docker Compose

Add to `docker-compose.yml`:

```yaml
services:
  langsmith-proxy:
    build: ./langsmith-proxy
    ports:
      - "8002:8002"
    environment:
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - LANGFUSE_HOST=${LANGFUSE_HOST:-https://cloud.langfuse.com}
      - LANGFUSE_DEBUG=${LANGFUSE_DEBUG:-false}
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8002/health').raise_for_status()"]
      interval: 30s
      timeout: 3s
      retries: 3
```

## API Endpoints

### LangSmith Compatible

- `POST /runs` - Create new run (trace/span/generation)
- `PATCH /runs/{run_id}` - Update run (completion, errors)
- `POST /runs/batch` - Batch create/update runs

### Proxy Specific

- `GET /health` - Health check
- `GET /info` - Proxy status and metrics

## Trace Mapping

| LangSmith Run Type | Langfuse Type | Description |
|--------------------|---------------|-------------|
| Root run           | Trace         | Top-level execution |
| `run_type: llm`    | Generation    | LLM completions |
| `run_type: chain`  | Span          | Agent chains |
| `run_type: tool`   | Span          | Tool calls |
| `run_type: retriever` | Span       | RAG retrievals |

## Example Usage

### Agent Service Configuration

```python
# agent-service/config/settings.py
import os

# Production: Use proxy
if os.getenv("ENVIRONMENT") == "production":
    os.environ["LANGCHAIN_ENDPOINT"] = "http://langsmith-proxy:8002"
    os.environ["LANGCHAIN_API_KEY"] = "dummy"
else:
    # Local dev: Use real LangSmith
    # Leave LANGCHAIN_ENDPOINT unset for default behavior
    pass
```

### Testing

```bash
# Start proxy
docker compose up langsmith-proxy

# Check health
curl http://localhost:8002/health

# Check proxy info
curl http://localhost:8002/info

# Run agent (will trace to Langfuse via proxy)
docker compose up agent-service
```

## Monitoring

The proxy logs all trace activity:

```
📊 Created Langfuse trace: agent_executor (run-abc123)
📍 Created Langfuse span: tool_call (run-xyz789)
🤖 Created Langfuse generation: llm_completion (run-def456)
✅ Completed Langfuse trace: agent_executor (run-abc123)
```

## Benefits

1. **Cost Savings**: No LangSmith cloud usage in production
2. **Unified Observability**: All traces in Langfuse
3. **Local Dev Flexibility**: Use LangSmith's UI for debugging
4. **Zero Code Changes**: Just environment variables
5. **Transparent**: LangGraph agents don't know they're using a proxy

## Limitations

- Proxy stores run mappings in memory (resets on restart)
- No LangSmith-specific features (datasets, evaluations)
- One-way sync (Langfuse → LangSmith not supported)

## Troubleshooting

### Traces not appearing in Langfuse

1. Check proxy logs: `docker logs langsmith-proxy`
2. Verify Langfuse credentials: `curl http://localhost:8002/health`
3. Ensure `LANGCHAIN_ENDPOINT` points to proxy

### Agent still using LangSmith cloud

1. Check `LANGCHAIN_ENDPOINT` is set correctly
2. Restart agent service after env change
3. Verify network connectivity: `docker compose exec agent-service ping langsmith-proxy`

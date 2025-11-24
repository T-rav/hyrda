# Agent Service

FastAPI service for executing LangGraph agents. Exposes agents as REST APIs that can be called from multiple clients.

## Architecture

The agent service provides a unified API for all LangGraph agents, making them accessible to:
- Slack bot
- LibreChat
- Web UI
- API clients

## Available Agents

- **help** - Help and documentation agent
- **profile** - Company profiling and research agent
- **meddic** - MEDDIC sales qualification agent
- **meddpicc_coach** - MEDDPICC coaching and insights agent

## API Endpoints

### List Agents
```bash
GET /api/agents
```

Returns list of all available agents with their metadata.

### Get Agent Info
```bash
GET /api/agents/{agent_name}
```

Returns detailed information about a specific agent.

### Invoke Agent (Synchronous)
```bash
POST /api/agents/{agent_name}/invoke
Content-Type: application/json

{
  "query": "Your query here",
  "context": {
    "user_id": "U123456",
    "channel": "C123456"
  }
}
```

Executes the agent and returns the complete response.

### Stream Agent (Streaming)
```bash
POST /api/agents/{agent_name}/stream
Content-Type: application/json

{
  "query": "Your query here",
  "context": {}
}
```

Returns a Server-Sent Events (SSE) stream with agent output.

## Local Development

### Install Dependencies
```bash
cd agent-service
pip install -e ".[dev]"
```

### Run Locally
```bash
# Set environment variables
export OPENAI_API_KEY=your-key
export VECTOR_HOST=localhost
export VECTOR_PORT=6333

# Run with hot reload
python app.py
```

The service will start on http://localhost:8000

### Run with Docker
```bash
docker compose up -d agent_service
```

## Environment Variables

Required:
- `LLM_PROVIDER` - LLM provider (openai, anthropic, etc.)
- `LLM_API_KEY` - API key for LLM provider
- `VECTOR_HOST` - Qdrant host
- `VECTOR_PORT` - Qdrant port

Optional:
- `PORT` - Service port (default: 8000)
- `ENVIRONMENT` - Environment (production, development)
- `LANGFUSE_ENABLED` - Enable Langfuse tracing
- `TAVILY_API_KEY` - For web search
- `PERPLEXITY_API_KEY` - For deep research

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html
```

## Integration with Bot

The Slack bot now calls this service via HTTP instead of running agents locally:

```python
import httpx

async def execute_agent(agent_name: str, query: str, context: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://agent_service:8000/api/agents/{agent_name}/invoke",
            json={"query": query, "context": context}
        )
        return response.json()
```

## Monitoring

- Health check: `GET /health`
- Metrics: Available through Prometheus metrics (if enabled)
- Logs: Structured JSON logs sent to Loki

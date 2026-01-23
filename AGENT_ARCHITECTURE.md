# Agent Service Architecture

The agent-service supports two types of agents, allowing gradual migration from local to cloud hosting.

## Agent Types

### 1. System Agents (Embedded LangGraph)
**Examples**: research, profile, meddic, help

**Characteristics**:
- LangGraph agents with state management
- Run in embedded LangGraph server within agent-service
- ALL agents are LangGraph agents (no separate "utility" agents)
- Can be migrated to cloud later without API changes

**Location**:
- System: `agent-service/agents/research/`, `agent-service/agents/help/`
- Custom: `custom_agents/profiler/`, `custom_agents/meddpicc_coach/`

**Execution**: agent-service FastAPI validates auth → invokes embedded LangGraph

**Config**: Defined in `langgraph.json` (auto-generated from merging system + custom configs)

**Use Case**: Default - all agents start here, can be moved to cloud later

---

### 2. Cloud Agents (Remote LangGraph)
**Examples**: Any embedded agent can become a cloud agent

**Characteristics**:
- Same LangGraph agents, but hosted remotely (LangSmith, separate cluster, etc.)
- agent-service proxies requests to remote `endpoint_url`
- Tracked in control-plane with `is_cloud: true`
- Gradual migration: move agents to cloud without changing client code

**Location**: External hosting (LangSmith, k8s cluster, etc.)

**Endpoint**: Proxied through agent-service's public API → remote `endpoint_url`

**Use Case**: Production scale-out, isolate resource-intensive agents, multi-region deployment

---

## Request Flow

### Non-Streaming Request
```
Client → POST /api/agents/research/invoke
    ↓
    ├─ Validate Auth (JWT/service token)
    ├─ Observability (metrics, tracing)
    └─ Control Plane (discover agent metadata)
        ↓
        ├─ Embedded? → agent.ainvoke() → Return complete response
        └─ Cloud? → HTTP POST to remote endpoint → Return response
```

### Streaming Request
```
Client → POST /api/agents/research/stream
    ↓
    ├─ Validate Auth (JWT/service token)
    ├─ Observability (metrics, tracing)
    └─ Control Plane (discover agent metadata)
        ↓
        ├─ Embedded? → agent.astream() → Yield SSE events
        └─ Cloud? → Proxy SSE from remote endpoint → Yield events
```

## Control Plane Integration

Agents are registered in control-plane with:
```json
{
  "name": "research",
  "is_cloud": false,
  "endpoint_url": "http://agent-service:8000/langgraph/threads"
}
```

or for cloud:
```json
{
  "name": "research",
  "is_cloud": true,
  "endpoint_url": "https://langsmith.com/api/v1/assistants/..."
}
```

## Configuration

### Embedded Agents (System & Custom)
**agent-service/agents/langgraph.json** (system agents):
```json
{
  "graphs": {
    "research": "agents.research.research_agent:research_agent"
  }
}
```

**custom_agents/langgraph.json** (custom agents):
```json
{
  "graphs": {
    "profile": "profiler.nodes.graph_builder:build_profile_researcher",
    "meddic": "meddpicc_coach.nodes.graph_builder:build_meddpicc_coach"
  }
}
```

**Merged at startup** → `agent-service/langgraph.json` (all embedded agents)

### Cloud Agents
Configured in control-plane database or via environment variables

## Migration Path

**Phase 1**: All agents embedded
```
agent-service (FastAPI + embedded LangGraph)
  ├─ research (embedded)
  ├─ profile (embedded)
  ├─ meddic (embedded)
  └─ help (embedded)
```

**Phase 2**: Migrate research to cloud
```
agent-service (FastAPI + embedded LangGraph)
  ├─ research → proxy → LangSmith Cloud
  ├─ profile (embedded)
  ├─ meddic (embedded)
  └─ help (embedded)
```

**Phase 3**: Full cloud
```
agent-service (FastAPI only, no embedded LangGraph)
  ├─ research → proxy → Cloud Cluster A
  ├─ profile → proxy → Cloud Cluster B
  ├─ meddic → proxy → Cloud Cluster C
  └─ help → proxy → Cloud Cluster D
```

## FastAPI Responsibilities

agent-service FastAPI is a **thin layer** that handles:

1. **Auth Validation** - Verify JWT tokens, service tokens, RBAC
2. **Observability** - Metrics (Prometheus), tracing (OpenTelemetry), logging
3. **Agent Discovery** - Query control-plane for agent metadata (`endpoint_url`, `is_cloud`)
4. **Routing**:
   - **Non-streaming**: `POST /api/agents/{name}/invoke`
     - Embedded → Invoke local LangGraph via `ainvoke()`
     - Cloud → HTTP POST to remote LangGraph endpoint
   - **Streaming**: `POST /api/agents/{name}/stream`
     - Embedded → Stream local LangGraph via `astream()`
     - Cloud → HTTP SSE stream from remote LangGraph endpoint
5. **Health Checks** - `/health`, `/ready` endpoints

**FastAPI does NOT execute agents** - it validates/routes, then calls LangGraph (local or remote).

### Streaming Support

Both embedded and cloud agents support **Server-Sent Events (SSE)** streaming:

```
Client → /api/agents/research/stream
  ↓
  ├─ Embedded? → agent.astream() → yield SSE events
  └─ Cloud? → Proxy SSE from remote endpoint
```

Client receives real-time updates as the agent executes (tool calls, reasoning steps, final response).

## API Endpoints

### Agent Execution
- `POST /api/agents/{name}/invoke` - Non-streaming agent invocation
- `POST /api/agents/{name}/stream` - Streaming agent invocation (SSE)
- `GET /api/agents` - List all registered agents
- `GET /api/agents/{name}` - Get agent metadata

### Observability
- `GET /health` - Health check
- `GET /api/metrics` - Prometheus metrics

### Example Request (Non-Streaming)
```bash
curl -X POST http://localhost:8000/api/agents/research/invoke \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Research quantum computing", "context": {}}'
```

### Example Request (Streaming)
```bash
curl -X POST http://localhost:8000/api/agents/research/stream \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Research quantum computing", "context": {}}'
```

## Benefits

✅ **Gradual Migration**: Move agents to cloud incrementally
✅ **No Client Changes**: Clients always call agent-service API
✅ **Unified Auth**: Single auth layer for embedded and cloud agents
✅ **Streaming & Non-Streaming**: Both modes supported for all agents
✅ **Cost Optimization**: Keep lightweight agents local, scale heavy agents in cloud
✅ **Multi-Region**: Deploy agents closer to users
✅ **Resource Isolation**: Isolate resource-intensive agents from system
✅ **Development Flexibility**: Develop locally, deploy to cloud
✅ **Unified Framework**: ALL agents use LangGraph (no special-case utility agents)

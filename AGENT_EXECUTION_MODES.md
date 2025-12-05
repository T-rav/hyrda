# Agent Execution Modes

InsightMesh supports two execution modes for agents: **Embedded** (local) and **Cloud** (LangGraph Platform).

## 🔌 External Agents Architecture

**All agents are externally loaded** - the Docker image ships with NO bundled agents. Agents are mounted from the `external_agents/` directory at runtime, giving clients full control:

- ✅ Remove agents you don't want
- ✅ Replace agents with your own versions
- ✅ Add new custom agents
- ✅ Update agents without rebuilding Docker image

See [`external_agents/README.md`](./external_agents/README.md) for complete agent customization guide.

## 🎯 Quick Reference

| Mode | Where Agents Run | Best For | Setup Complexity |
|------|------------------|----------|------------------|
| **Embedded** | agent-service container | Development, full control | ✅ Simple (default) |
| **Cloud** | LangGraph Platform | Production, scaling | ⚠️ Requires LangGraph Cloud |

**Switch mode via single environment variable:**
```bash
AGENT_EXECUTION_MODE=embedded  # or "cloud"
```

---

## 🏠 Embedded Mode (Default)

### What It Is
Agents run as Python code inside the `agent-service` Docker container.

### When to Use
- ✅ Local development (fast iteration)
- ✅ Full control over execution environment
- ✅ No external dependencies
- ✅ Cost-sensitive deployments (no platform fees)

### Configuration
```bash
# .env (default - no config needed)
AGENT_EXECUTION_MODE=embedded
```

### Architecture
```
Bot → Agent-Service (runs agents in-process) → OpenAI
```

### Pros
- Zero external dependencies
- Fast local development/debugging
- No additional costs
- Full control over agent code

### Cons
- Requires agent-service restart to deploy new agents
- Manual scaling (need to run multiple containers)
- No built-in deployment versioning

---

## ☁️ Cloud Mode

### What It Is
Agents run on LangGraph Cloud (managed by LangChain). Agent-service becomes a thin proxy.

### When to Use
- ✅ Production deployments
- ✅ Need independent agent deployments (no restarts)
- ✅ Auto-scaling requirements
- ✅ Want built-in LangSmith tracing
- ✅ Multiple environments (dev/staging/prod with different versions)

### Configuration
```bash
# .env
AGENT_EXECUTION_MODE=cloud
LANGGRAPH_CLOUD_URL=https://your-deployment.langraph.api
LANGGRAPH_API_KEY=lsv2_pt_your-key-here
```

### Architecture
```
Bot → Agent-Service (proxy) → LangGraph Cloud → OpenAI
              ↓
    Control-Plane (stores assistant_id for routing)
```

### Pros
- Deploy agents without restarting services
- Auto-scaling by LangGraph Platform
- Version management (rollback, canary)
- Built-in LangSmith tracing
- Independent agent lifecycles

### Cons
- External dependency (LangGraph Cloud)
- Additional cost (~$20-200/mo based on usage)
- Requires deployment workflow

---

## 🔄 Switching Modes

### From Embedded to Cloud

**Prerequisites:**
- LangGraph Cloud account: https://langchain-ai.github.io/langgraph/cloud/
- Deploy agents to LangGraph Cloud (external to this system)

**Steps:**

1. **Deploy agents to LangGraph Cloud** (external):
```bash
# Using LangGraph CLI
langgraph deploy --graph agent-service/agents/profile_agent.py --name profile

# Returns assistant_id (e.g., "asst_abc123")
```

2. **Register assistant_id in control-plane**:
```sql
-- Via database update
UPDATE agent_metadata
SET langgraph_assistant_id = 'asst_abc123',
    langgraph_url = 'https://your-deployment.langraph.api'
WHERE agent_name = 'profile';

-- Or via control-plane UI (when available)
```

3. **Update environment variables**:
```bash
# .env
AGENT_EXECUTION_MODE=cloud
LANGGRAPH_CLOUD_URL=https://your-deployment.langraph.api
LANGGRAPH_API_KEY=lsv2_pt_your-key
```

4. **Restart agent-service**:
```bash
docker compose restart agent_service
```

5. **Verify**:
```bash
# Check logs for cloud mode initialization
docker logs insightmesh-agent-service 2>&1 | grep "CLOUD"
# Should see: "Agent execution mode: CLOUD (LangGraph Platform @ ...)"
```

### From Cloud to Embedded

1. **Update .env**:
```bash
AGENT_EXECUTION_MODE=embedded
# Remove or comment out:
# LANGGRAPH_CLOUD_URL=...
# LANGGRAPH_API_KEY=...
```

2. **Restart agent-service**:
```bash
docker compose restart agent_service
```

---

## 🎭 Hybrid Approach (Recommended)

Run different modes per environment:

```bash
# Development (.env.dev)
AGENT_EXECUTION_MODE=embedded

# Staging (.env.staging)
AGENT_EXECUTION_MODE=cloud
LANGGRAPH_CLOUD_URL=https://staging.langraph.api

# Production (.env.prod)
AGENT_EXECUTION_MODE=cloud
LANGGRAPH_CLOUD_URL=https://prod.langraph.api
```

**Benefits:**
- Fast local iteration (embedded)
- Production-ready deployment (cloud)
- Test cloud deployment in staging
- Cost-effective (only pay for staging/prod)

---

## 📊 Observability Per Mode

### Embedded Mode
- **Infrastructure**: OpenTelemetry + Jaeger (HTTP traces)
- **LLM Calls**: Langfuse (agent reasoning, tool calls)
- **Metrics**: Prometheus (request rates, latency)

### Cloud Mode
- **Infrastructure**: OpenTelemetry + Jaeger (HTTP proxy traces)
- **LLM Calls**: LangSmith (built-in to LangGraph Cloud)
- **Agent Execution**: LangSmith (automatic tracing)
- **Metrics**: Prometheus (proxy layer)

**Note:** In cloud mode, LangSmith replaces Langfuse for agent/LLM tracing.

---

## 🚨 Important Notes

### Control-Plane Role
- **Embedded mode**: Stores agent metadata (name, permissions, description)
- **Cloud mode**: Stores metadata + `langgraph_assistant_id` for routing
- **Does NOT deploy agents**: Deployment happens externally (LangGraph CLI, Studio, API)
- **Source of truth**: Control-plane registry determines which agents exist

### Bot Service
- **Unchanged**: Always calls `agent-service` HTTP API
- **Unaware**: Doesn't know or care about execution mode
- **Transparent**: Execution mode is an agent-service implementation detail

### Agent-Service Role
- **Embedded mode**: Runs agents
- **Cloud mode**: Proxies requests to LangGraph Cloud
- **Routes**: Based on `AGENT_EXECUTION_MODE` env var

---

## 🛠️ Troubleshooting

### "Agent not deployed to LangGraph Cloud"
**Error**: `ValueError: Agent 'profile' not deployed to LangGraph Cloud`

**Fix**: Register `assistant_id` in control-plane:
```sql
UPDATE agent_metadata
SET langgraph_assistant_id = 'asst_xyz'
WHERE agent_name = 'profile';
```

### "LANGGRAPH_CLOUD_URL required"
**Error**: `ValueError: AGENT_EXECUTION_MODE=cloud requires LANGGRAPH_CLOUD_URL`

**Fix**: Add credentials to `.env`:
```bash
LANGGRAPH_CLOUD_URL=https://your-deployment.langraph.api
LANGGRAPH_API_KEY=lsv2_pt_your-key
```

### "Module langgraph_sdk not found"
**Fix**: LangGraph SDK missing (only needed in cloud mode). Rebuild agent-service:
```bash
docker compose build agent_service
```

---

## 📚 Additional Resources

- **LangGraph Cloud Docs**: https://langchain-ai.github.io/langgraph/cloud/
- **LangSmith**: https://smith.langchain.com/
- **Control-Plane UI**: http://localhost:6001 (agent registry)
- **Agent-Service Logs**: `docker logs insightmesh-agent-service`

---

## 🎨 Agent Deployment Patterns

### Pattern 1: Use Provided Agents (Default)
```yaml
# docker-compose.yml (unchanged)
volumes:
  - ./external_agents:/app/external_agents:ro  # Mount provided agents
```

Agents available: `profile`, `meddic`

### Pattern 2: Custom Agent Selection
```bash
# Remove agents you don't want
rm -rf external_agents/meddic

# Add your own
mkdir external_agents/my_agent
# ... create agent.py ...

# Restart
docker compose restart agent_service
```

### Pattern 3: Completely Custom Agents
```bash
# Remove all provided agents
rm -rf external_agents/profile external_agents/meddic

# Add only your agents
mkdir external_agents/agent1
mkdir external_agents/agent2

# Restart
docker compose restart agent_service
```

### Pattern 4: Git-Based Agent Repository
```bash
# Client maintains agents in separate repo
git clone https://github.com/client/custom-agents.git external_agents

# docker-compose.yml
volumes:
  - ./external_agents:/app/external_agents:ro
```

**Benefits:**
- Version control for agents
- Easy rollback
- Team collaboration
- CI/CD integration

### Pattern 5: Hot-Reload Development
```yaml
# docker-compose.dev.yml
volumes:
  - ./external_agents:/app/external_agents:rw  # Read-write for development
```

```bash
# Edit agents without restarting
vim external_agents/profile/prompts.py

# Reload specific agent
curl -X POST http://localhost:8000/api/agents/profile/reload
```

---

**Last Updated**: 2025-12-05

# Agent Loading Architecture

## 🎯 Design Principles

1. **Single Source of Truth**: Control-plane database stores ALL agent metadata
2. **Mode-Agnostic Registry**: `agent_registry.py` works for both embedded and cloud modes
3. **Clean Abstraction**: `AgentExecutor` routes execution, doesn't know about agent loading
4. **External Agents**: All agent code lives in `external_agents/` (client-customizable)

---

## 📐 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Control-Plane Database                          │
│                   (Single Source of Truth)                           │
│                                                                       │
│  agent_metadata table:                                               │
│  ├─ agent_name: "profile"                                            │
│  ├─ display_name: "Company Profiler"                                 │
│  ├─ description: "..."                                                │
│  ├─ aliases: ["profiler", "research"]                                │
│  ├─ langgraph_assistant_id: "asst_123" (cloud mode only)             │
│  ├─ is_public: true                                                  │
│  └─ requires_admin: false                                            │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
                   HTTP GET /api/agents (with TTL cache)
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    agent_registry.py                                 │
│                  (Mode-Agnostic Registry)                            │
│                                                                       │
│  1. get_agent_registry():                                            │
│     - Fetches agent list from control-plane API                      │
│     - Caches for 5 minutes (TTL)                                     │
│                                                                       │
│  2. _load_agent_classes():                                           │
│     - Discovers agents in external_agents/                           │
│     - Loads Agent classes from agent.py files                        │
│     - Called automatically on first access                           │
│                                                                       │
│  3. Merges metadata + classes:                                       │
│     {                                                                 │
│       "profile": {                                                    │
│         "name": "profile",                                            │
│         "display_name": "Company Profiler",                           │
│         "agent_class": ProfileResearcher,  ← From external_agents    │
│         "langgraph_assistant_id": "asst_123"  ← From control-plane   │
│       }                                                               │
│     }                                                                 │
│                                                                       │
│  4. get_agent(name) → Agent instance:                                │
│     - Looks up agent_info                                            │
│     - Instantiates agent_class()                                     │
│     - Returns ready-to-invoke agent                                  │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      AgentExecutor                                   │
│                    (Execution Router)                                │
│                                                                       │
│  Mode: EMBEDDED                    Mode: CLOUD                       │
│  ├─ get_agent(name)                ├─ get_agent_info(name)           │
│  ├─ agent.invoke()                 ├─ Extract assistant_id           │
│  └─ Return result                  ├─ Call LangGraph Cloud           │
│                                    └─ Return result                  │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   FastAPI Endpoints                                  │
│                   (Public API)                                       │
│                                                                       │
│  POST /api/agents/{agent_name}/invoke                                │
│  GET  /api/agents                                                    │
│  POST /api/agents/{agent_name}/reload (dev only)                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow

### Embedded Mode (Default)

```
1. Request: POST /api/agents/profile/invoke
   ↓
2. AgentExecutor.invoke_agent("profile", query, context)
   ↓ (mode == EMBEDDED)
3. AgentExecutor._invoke_embedded()
   ↓
4. agent_registry.get_agent("profile")
   ↓
5. agent_registry.get_agent_info("profile")
   ├─ Fetches from control-plane API (cached)
   ├─ Merges with external_agent_loader classes
   └─ Returns: {"name": "profile", "agent_class": ProfileResearcher, ...}
   ↓
6. agent_class() → ProfileResearcher instance
   ↓
7. agent.invoke(query, context)
   ↓
8. Return {"response": "...", "metadata": {...}}
```

### Cloud Mode

```
1. Request: POST /api/agents/profile/invoke
   ↓
2. AgentExecutor.invoke_agent("profile", query, context)
   ↓ (mode == CLOUD)
3. AgentExecutor._invoke_cloud()
   ↓
4. AgentExecutor._get_agent_metadata("profile")
   ├─ Fetches from control-plane API
   └─ Returns: {"name": "profile", "langgraph_assistant_id": "asst_123", ...}
   ↓
5. Extract assistant_id
   ↓
6. LangGraph Cloud API:
   ├─ Create thread
   ├─ Create run with assistant_id
   └─ Wait for completion
   ↓
7. Return result from LangGraph Cloud
```

---

## 📝 Key Design Decisions

### 1. Why Control-Plane is Source of Truth

**✅ Pros:**
- Single place to enable/disable agents
- Consistent agent list across embedded and cloud modes
- Centralized permissions (is_public, requires_admin)
- Easy to add new agents without code deployment

**❌ Cons:**
- Requires database to be up
- Adds network hop (mitigated by caching)

**Decision:** Worth the trade-off for consistency

### 2. Why External Agent Loader

**✅ Pros:**
- Clients can customize agents without rebuilding image
- Git-based agent workflows
- Hot-reload for development

**❌ Cons:**
- Agents must be registered in two places (control-plane + external_agents/)
- Possible mismatch if not synced

**Decision:** Document sync process, worth the flexibility

### 3. Why Agent Registry Caches

**✅ Pros:**
- Reduces control-plane load
- Fast agent lookups
- Auto-refresh every 5 minutes

**❌ Cons:**
- 5-minute lag for new agents
- Can call `clear_cache()` to force refresh

**Decision:** Good balance of performance vs freshness

---

## 🔍 Component Responsibilities

### Control-Plane (`control_plane/`)
- **Stores**: Agent metadata (name, description, aliases, cloud settings)
- **Provides**: REST API at `GET /api/agents`
- **Validates**: Agent permissions, user access
- **Does NOT**: Load agent code, execute agents

### Agent Registry (`agent-service/services/agent_registry.py`)
- **Fetches**: Agent list from control-plane
- **Loads**: Agent classes from external_agents/
- **Merges**: Metadata + classes into unified registry
- **Caches**: Result for 5 minutes
- **Provides**: `get_agent(name)` → instance

### External Agent Loader (`agent-service/services/external_agent_loader.py`)
- **Discovers**: Agents in external_agents/ directory
- **Loads**: Agent classes from agent.py files
- **Validates**: Agent has required Agent class
- **Supports**: Hot-reload for development
- **Does NOT**: Know about control-plane

### Agent Executor (`agent-service/services/agent_executor.py`)
- **Routes**: Execution based on AGENT_EXECUTION_MODE
- **Embedded**: Calls `get_agent()` → `agent.invoke()`
- **Cloud**: Calls LangGraph Cloud API with assistant_id
- **Does NOT**: Load agents, manage registry

---

## 🧪 Testing Strategy

### Unit Tests
- `test_agent_registry.py` - Registry logic, caching, merging
- `test_external_agent_loader.py` - Agent discovery, loading, reload
- `test_agent_executor.py` - Mode routing, embedded/cloud execution

### Integration Tests
- End-to-end: FastAPI → AgentExecutor → agent.invoke()
- Control-plane sync: Register agent → appears in registry
- Cloud mode: Mock LangGraph Cloud API

---

## 🚨 Common Issues

### Issue: Agent in Control-Plane but Not Loading

**Symptom:**
```
ValueError: Agent 'profile' found in control-plane but no implementation available
```

**Cause**: Agent registered in database but `external_agents/profile/agent.py` missing

**Fix**:
```bash
ls external_agents/profile/agent.py  # Check file exists
docker compose restart agent_service  # Reload
```

### Issue: Agent in External but Not Available

**Symptom:** Agent loads but can't be invoked

**Cause**: Agent not registered in control-plane database

**Fix**:
```sql
INSERT INTO agent_metadata (agent_name, display_name, is_public)
VALUES ('my_agent', 'My Agent', true);
```

### Issue: Stale Agent List After Changes

**Symptom:** New agent not appearing

**Cause**: 5-minute registry cache

**Fix**:
```bash
# Force reload via API
curl -X POST http://localhost:8000/api/agents/reload-all

# Or restart service
docker compose restart agent_service
```

---

## 📚 Related Documentation

- [External Agents README](./external_agents/README.md) - How to create/customize agents
- [Agent Execution Modes](./AGENT_EXECUTION_MODES.md) - Embedded vs Cloud deployment
- [Control-Plane API](./control_plane/README.md) - Agent registry management
- [Agent-to-Slack Output Contract](./docs/AGENT_SLACK_CONTRACT.md) - Standardized output format for Slack integration

---

**Last Updated**: 2025-12-05
**Architecture Version**: 2.0 (External Agents)

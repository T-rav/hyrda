# External Agents Directory

This directory contains **all agents** for InsightMesh. Agents are **externally loaded** at runtime, allowing you to:

- ✅ Remove agents you don't want
- ✅ Replace agents with your own versions
- ✅ Add new custom agents
- ✅ Modify existing agents without rebuilding Docker image

## 🎯 Key Concept

**The Docker image ships with NO bundled agents.** This directory is mounted into the container at runtime, giving you full control over which agents are available.

---

## 📁 Directory Structure

```
external_agents/
├── README.md (this file)
├── profile/              # Company profiling agent (provided by default)
│   ├── agent.py          # Entry point (REQUIRED)
│   ├── profile_researcher.py
│   ├── tools/
│   └── ...
├── meddic/               # Sales qualification agent (provided by default)
│   ├── agent.py          # Entry point (REQUIRED)
│   ├── meddpicc_coach.py
│   └── ...
└── your_custom_agent/    # Your custom agents go here
    ├── agent.py          # Entry point (REQUIRED)
    └── ...
```

---

## 🚀 Quick Start: Add a New Agent

### 1. Create Agent Directory

```bash
mkdir -p external_agents/my_agent
```

###  2. Create `agent.py` Entry Point

Every agent MUST have an `agent.py` file with an `Agent` class:

```python
# external_agents/my_agent/agent.py
"""My Custom Agent - Does amazing things."""

class Agent:
    """Custom agent implementation."""

    def __init__(self):
        """Initialize agent."""
        self.name = "my_agent"

    async def invoke(self, query: str, context: dict) -> dict:
        """Process user query.

        Args:
            query: User's question/request
            context: Additional context (user_id, channel, etc.)

        Returns:
            dict with 'response' and 'metadata' keys
        """
        # Your agent logic here
        response = f"Processed: {query}"

        return {
            "response": response,
            "metadata": {
                "agent": self.name,
                "success": True
            }
        }
```

### 3. Register in Control-Plane

Agents must be registered in the control-plane database:

```sql
-- Via MySQL
INSERT INTO agent_metadata (agent_name, display_name, description, aliases, is_public, requires_admin)
VALUES ('my_agent', 'My Agent', 'Does amazing things', '["my","custom"]', true, false);
```

Or via control-plane UI: http://localhost:6001

### 4. Restart Agent Service

```bash
docker compose restart agent_service
```

### 5. Test Your Agent

```bash
# Via Slack
@bot invoke my_agent What can you do?

# Or via API
curl http://localhost:8000/api/agents/my_agent/invoke \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "What can you do?", "context": {}}'
```

---

## 📝 Agent Requirements

### **REQUIRED: `agent.py` File**

Every agent directory MUST contain `agent.py` with an `Agent` class.

**Minimal Template:**

```python
# agent.py
class Agent:
    async def invoke(self, query: str, context: dict) -> dict:
        return {"response": "Hello!", "metadata": {}}
```

### **REQUIRED: `invoke()` Method**

The `Agent` class MUST have an `async invoke()` method:

```python
async def invoke(self, query: str, context: dict) -> dict:
    """
    Args:
        query (str): User's question/request
        context (dict): Additional context
            - user_id: Slack user ID
            - channel_id: Slack channel ID
            - thread_ts: Slack thread timestamp
            - other custom fields

    Returns:
        dict: Response dictionary with:
            - response (str): Main response text
            - metadata (dict): Optional metadata
    """
```

---

## 🎨 Agent Patterns

### **Pattern 1: Simple Agent (Single File)**

```python
# agent.py
class Agent:
    async def invoke(self, query: str, context: dict) -> dict:
        response = f"Received: {query}"
        return {"response": response, "metadata": {}}
```

### **Pattern 2: Agent with Separate Logic**

```
my_agent/
├── agent.py           # Entry point (exports Agent)
├── logic.py           # Core logic
└── tools.py           # Helper functions
```

```python
# agent.py
from logic import process_query

class Agent:
    async def invoke(self, query: str, context: dict) -> dict:
        result = await process_query(query)
        return {"response": result, "metadata": {}}
```

### **Pattern 3: LangGraph Agent (Advanced)**

```python
# agent.py
from langgraph.graph import StateGraph
from state import AgentState

class Agent:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        # Add nodes and edges
        return workflow.compile()

    async def invoke(self, query: str, context: dict) -> dict:
        result = await self.graph.ainvoke({"messages": [query]})
        return {"response": result["response"], "metadata": {}}
```

---

## 🔧 Customizing Existing Agents

### **Remove an Agent**

```bash
# Simply delete the directory
rm -rf external_agents/meddic

# Restart service
docker compose restart agent_service
```

### **Replace an Agent**

```bash
# Backup original
mv external_agents/profile external_agents/profile_original

# Create your version
mkdir external_agents/profile
# ... add your agent.py ...

# Restart service
docker compose restart agent_service
```

### **Modify an Agent**

```bash
# Edit directly
vim external_agents/profile/prompts.py

# For development: Enable hot-reload (see below)
```

---

## 🔥 Hot-Reload for Development

For rapid iteration without restarting the container:

### 1. Add Reload Endpoint (Already Included)

The agent-service includes a reload endpoint.

### 2. Reload Specific Agent

```bash
# Reload agent after editing
curl -X POST http://localhost:8000/api/agents/profile/reload
```

### 3. Reload All Agents

```bash
# Force re-discovery of all agents
curl -X POST http://localhost:8000/api/agents/reload-all
```

**Note:** Hot-reload works for Python code changes but not for new dependencies.

---

## 📦 Dependencies

### **Built-in Dependencies**

These are already available in the Docker image:

- `langgraph`
- `langchain`
- `openai`
- `anthropic`
- `requests`
- `httpx`
- All shared utilities

### **Custom Dependencies**

If your agent needs additional packages:

#### Option 1: Request Addition to Docker Image

Create a PR to add to `agent-service/requirements.txt`

#### Option 2: Install at Runtime (Development Only)

```bash
# Not recommended for production
docker exec insightmesh-agent-service pip install your-package
```

#### Option 3: Custom Docker Image

Build your own image extending ours:

```dockerfile
FROM insightmesh-agent-service:latest
RUN pip install your-custom-packages
```

---

## 🧪 Testing Your Agent

### **Unit Tests**

```python
# external_agents/my_agent/test_agent.py
import pytest
from agent import Agent

@pytest.mark.asyncio
async def test_agent_invoke():
    agent = Agent()
    result = await agent.invoke("test query", {})
    assert "response" in result
    assert result["response"] is not None
```

Run tests:

```bash
pytest external_agents/my_agent/test_agent.py
```

### **Integration Tests**

```bash
# Test via API
curl -X POST http://localhost:8000/api/agents/my_agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "context": {}}'
```

### **Slack Tests**

```
@bot invoke my_agent test query
```

---

## 🚨 Troubleshooting

### **Agent Not Found**

```
Error: Agent 'my_agent' not found
```

**Solutions:**
1. Check agent directory exists: `ls external_agents/my_agent`
2. Check `agent.py` exists: `ls external_agents/my_agent/agent.py`
3. Check logs: `docker logs insightmesh-agent-service | grep my_agent`
4. Restart service: `docker compose restart agent_service`

### **Module Import Errors**

```
ImportError: No module named 'my_module'
```

**Solutions:**
1. Ensure relative imports: `from .my_module import func`
2. Check file exists in agent directory
3. Add `__init__.py` if using package structure

### **Agent Class Not Found**

```
AttributeError: module has no attribute 'Agent'
```

**Solutions:**
1. Ensure `agent.py` defines `Agent` class
2. Check class name is exactly `Agent` (case-sensitive)
3. Verify class is not nested inside another class

### **No Agents Loaded**

```
⚠️ No agents loaded! Ensure EXTERNAL_AGENTS_PATH is set and agents directory is mounted
```

**Solutions:**
1. Check volume mount in `docker-compose.yml`:
   ```yaml
   volumes:
     - ./external_agents:/app/external_agents:ro
   ```
2. Check environment variable:
   ```yaml
   environment:
     - EXTERNAL_AGENTS_PATH=/app/external_agents
   ```
3. Restart: `docker compose down && docker compose up -d`

---

## 📚 Examples

See the provided agents for complete examples:

- **`profile/`**: LangGraph agent with complex workflow
- **`meddic/`**: Sales qualification coach

Study these to understand:
- LangGraph state management
- Tool integration
- Prompt engineering
- Error handling
- Metadata tracking

---

## 🔐 Security Notes

1. **Read-Only Mount**: Agents are mounted `:ro` (read-only) in production
2. **Code Review**: Review agent code before deployment
3. **Permissions**: Agents run with same permissions as agent-service
4. **Secrets**: Use environment variables for API keys, never hardcode

---

## 📖 Additional Resources

- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Control-Plane UI**: http://localhost:6001
- **Agent Service API**: http://localhost:8000/docs
- **Main Docs**: See `AGENT_EXECUTION_MODES.md` in project root

---

**Last Updated**: 2025-12-05
**Version**: 1.0

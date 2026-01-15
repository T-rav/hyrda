# Retrieval API for Agents

## Overview

The new `/api/v1/retrieve` endpoint provides **retrieval-only** access to the vector database, allowing agents to:
- Get relevant chunks without calling the LLM
- Apply custom filters based on user permissions
- Use system_message for contextual retrieval
- Call their own LLM in their graph flow

## Why This Architecture?

### Before (Current):
```
agent-service has direct Qdrant client
  ↓
- Duplicate Qdrant connection logic
- Hard to add permissions/filtering
- No centralized tracing
- Agents coupled to Qdrant
```

### After (New):
```
agent-service → rag-service /retrieve → Qdrant
  ↓
- Single source of truth for vector access
- Centralized permissions/filtering
- All retrievals traced to Langfuse
- Agents decoupled from vector DB
```

## Benefits

### ✅ Single Abstraction for Internal Fetching
- **One place** to manage vector database access
- **One place** to add permissions logic
- **One place** to trace retrievals
- **One place** to optimize queries

### ✅ System Message for Filtering
```python
# Agent can inject user context for filtering
response = await http_client.post("/api/v1/retrieve", {
    "query": "Show me project files",
    "system_message": "User: john@8thlight.com\nRole: consultant\nProjects: A, B, C",
    "max_chunks": 10
})

# rag-service can use system_message to:
# - Filter by accessible projects
# - Apply role-based permissions
# - Log user context for audit
```

### ✅ No Direct Qdrant Dependency
- Agents don't need Qdrant client
- Agents don't need SSL certificates
- Agents don't manage connections
- Easier testing (mock HTTP instead of Qdrant)

### ✅ Centralized Observability
```
All retrievals traced to Langfuse:
- Which agent retrieved what
- What queries were made
- What chunks were returned
- User/permission context
```

### ✅ Easy to Enhance
Want to add new features? Just update rag-service:
- Permission-based filtering → Add to /retrieve
- Semantic caching → Add to /retrieve
- Rate limiting → Add to /retrieve
- Audit logging → Add to /retrieve

All agents get the feature automatically!

## API Reference

### Endpoint
```
POST /api/v1/retrieve
POST /api/retrieve  (alias)
```

### Request Body
```json
{
  "query": "Search query",
  "user_id": "user@example.com",
  "system_message": "User: john@8thlight.com\nRole: consultant\nProjects: A, B, C",
  "max_chunks": 10,
  "similarity_threshold": 0.7,
  "filters": {
    "source": "google_drive",
    "project": "Project A"
  },
  "conversation_history": [
    {"role": "user", "content": "Previous question"},
    {"role": "assistant", "content": "Previous answer"}
  ],
  "enable_query_rewriting": true
}
```

### Response
```json
{
  "chunks": [
    {
      "content": "Document chunk text...",
      "metadata": {
        "file_name": "financial_report_q4.pdf",
        "source": "google_drive",
        "page": 5,
        "project": "Project A"
      },
      "similarity": 0.95,
      "chunk_id": "chunk_abc123"
    }
  ],
  "metadata": {
    "total_chunks": 10,
    "unique_sources": 3,
    "avg_similarity": 0.87,
    "similarity_threshold": 0.7,
    "query_rewritten": true,
    "service": "agent-service"
  }
}
```

## Agent Usage Examples

### Example 1: Company Profile Agent

**Before (Direct Qdrant):**
```python
# agent-service/agents/company_profile/tools/internal_search.py
from qdrant_client import QdrantClient

class InternalSearchTool(BaseTool):
    qdrant_client: QdrantClient  # Direct dependency

    async def _arun(self, query: str):
        # Manual Qdrant query
        results = self.qdrant_client.search(
            collection_name="insightmesh_docs",
            query_vector=embedding,
            limit=10
        )
        return results
```

**After (HTTP Retrieval API):**
```python
# agent-service/agents/company_profile/tools/internal_search.py
import httpx

class InternalSearchTool(BaseTool):
    rag_service_url: str = "http://rag-service:8002"

    async def _arun(self, query: str, user_permissions: dict = None):
        # Build system message with permissions
        system_message = None
        if user_permissions:
            system_message = f"""
User: {user_permissions.get('user_id')}
Role: {user_permissions.get('role')}
Accessible Projects: {', '.join(user_permissions.get('projects', []))}
            """.strip()

        # Call retrieval API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.rag_service_url}/api/v1/retrieve",
                json={
                    "query": query,
                    "user_id": user_permissions.get('user_id') if user_permissions else None,
                    "system_message": system_message,
                    "max_chunks": 10,
                    "similarity_threshold": 0.75,
                    "filters": {
                        "project": user_permissions.get('projects', [])
                    } if user_permissions else None
                },
                headers={
                    "X-Service-Token": os.getenv("RAG_SERVICE_TOKEN"),
                    "X-User-Email": user_permissions.get('user_id') if user_permissions else "agent@system"
                }
            )
            data = response.json()
            return data['chunks']
```

### Example 2: Lead Qualifier Agent

```python
# agent-service/agents/lead_qualifier/graph.py

async def research_node(state: AgentState):
    """Research node that uses retrieval API."""
    company_name = state['company_name']

    # Retrieve internal docs about company
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://rag-service:8002/api/v1/retrieve",
            json={
                "query": f"Previous engagements with {company_name}",
                "max_chunks": 5,
                "similarity_threshold": 0.8,
                "filters": {
                    "document_type": ["client_notes", "project_docs"]
                }
            },
            headers={
                "X-Service-Token": os.getenv("RAG_SERVICE_TOKEN"),
                "X-User-Email": "lead_qualifier_agent@system"
            }
        )

        chunks = response.json()['chunks']

        # Now use chunks in LLM call (agent controls the LLM)
        llm = ChatOpenAI(model="gpt-4")
        prompt = f"""
Analyze this company for qualification:
Company: {company_name}

Internal knowledge:
{format_chunks(chunks)}

Provide qualification score and reasoning.
"""
        result = await llm.ainvoke(prompt)

        state['research_results'] = result
        return state
```

### Example 3: Permission-Aware Retrieval

```python
# Agent retrieves only what user has access to

user_context = {
    "user_id": "john@8thlight.com",
    "role": "consultant",
    "projects": ["Project A", "Project B"],
    "clearance": "confidential"
}

# Inject permissions into retrieval
response = await http_client.post("/api/v1/retrieve", {
    "query": "Show me all technical specifications",
    "system_message": f"""
User: {user_context['user_id']}
Role: {user_context['role']}
Accessible Projects: {', '.join(user_context['projects'])}
Clearance Level: {user_context['clearance']}
    """,
    "filters": {
        "project": user_context['projects'],
        "clearance_level": ["public", "confidential"]  # Exclude "secret"
    }
})

# Returns ONLY chunks user has permission to see
```

## Migration Path

### Phase 1: Add New Endpoint (Done ✅)
- Create `/api/v1/retrieve` endpoint
- Add to rag-service app.py
- Test with curl/Postman

### Phase 2: Update One Agent
1. Pick one agent (e.g., Company Profile)
2. Replace direct Qdrant calls with HTTP retrieve calls
3. Test thoroughly
4. Compare performance

### Phase 3: Roll Out to All Agents
- Update all agents to use `/retrieve`
- Remove Qdrant dependencies from agent-service
- Update docker-compose (agent-service no longer needs Qdrant connection)

### Phase 4: Add Enhancements
Now that all retrieval is centralized:
- Add permission-based filtering
- Add semantic caching
- Add rate limiting
- Add detailed audit logging

## Testing

### Curl Example
```bash
curl -X POST http://localhost:8002/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: your-service-token" \
  -H "X-User-Email: test@example.com" \
  -d '{
    "query": "What is our Q4 revenue?",
    "max_chunks": 5,
    "similarity_threshold": 0.7
  }'
```

### Python Example
```python
import httpx
import os

async def test_retrieve():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/api/v1/retrieve",
            json={
                "query": "What is our Q4 revenue?",
                "max_chunks": 5,
                "similarity_threshold": 0.7
            },
            headers={
                "X-Service-Token": os.getenv("RAG_SERVICE_TOKEN"),
                "X-User-Email": "test@example.com"
            }
        )
        data = response.json()
        print(f"Retrieved {len(data['chunks'])} chunks")
        for chunk in data['chunks']:
            print(f"- {chunk['metadata']['file_name']} (similarity: {chunk['similarity']:.2f})")
```

## Comparison

| Aspect | Direct Qdrant | Retrieval API |
|--------|---------------|---------------|
| **Vector Access** | Multiple services | Single service |
| **Permissions** | Hard to implement | Centralized |
| **Tracing** | Manual | Automatic |
| **Filtering** | Per-service logic | Shared logic |
| **Testing** | Need Qdrant mock | HTTP mock |
| **SSL Certs** | Every service | rag-service only |
| **Observability** | Scattered | Centralized |
| **Caching** | Per-service | Shared cache |
| **Rate Limiting** | Per-service | Centralized |

## Future Enhancements

Once all retrieval is centralized, we can add:

### 1. Permission-Based Filtering
```python
# rag-service/api/retrieve.py
def apply_permissions(chunks, user_permissions):
    """Filter chunks based on user permissions."""
    filtered = []
    for chunk in chunks:
        project = chunk['metadata'].get('project')
        if project in user_permissions.get('projects', []):
            filtered.append(chunk)
    return filtered
```

### 2. Semantic Caching
```python
# Cache similar queries
if cached := semantic_cache.get(query_embedding):
    return cached['chunks']
```

### 3. Multi-Tenancy
```python
# Isolate data by organization
filters["organization_id"] = user.organization_id
```

### 4. Audit Logging
```python
# Log all retrievals for compliance
audit_log.record_retrieval(
    user_id=user_id,
    query=query,
    chunks_returned=len(chunks),
    timestamp=datetime.now()
)
```

## Summary

✅ **Single abstraction for internal fetching**
- One place for vector access
- Easy to enhance and maintain

✅ **System message for permissions**
- Inject user context
- Filter based on roles/projects

✅ **Decoupled architecture**
- Agents don't depend on Qdrant
- Easy to test and mock

✅ **Centralized observability**
- All retrievals traced
- Better monitoring and debugging

**This is the right architectural move!** 🎯

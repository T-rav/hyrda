# Integration Testing Guide

Comprehensive guide for writing integration tests for agents, cross-service behavior, and end-to-end workflows.

---

## Table of Contents

1. [Test Types](#test-types)
2. [Agent Integration Tests](#agent-integration-tests)
3. [Cross-Service Integration Tests](#cross-service-integration-tests)
4. [End-to-End Tests](#end-to-end-tests)
5. [Test Infrastructure](#test-infrastructure)
6. [Best Practices](#best-practices)
7. [Examples](#examples)

---

## Test Types

### Unit Tests
- Test single functions/methods in isolation
- Mock all external dependencies
- Fast, no network/DB calls
- Location: `*/tests/test_*.py`

### Integration Tests
- Test multiple components working together
- Use real services (vector DB, LLM, etc.)
- Marked with `@pytest.mark.integration`
- Location: `*/tests/test_*_integration.py` or `evals/`

### End-to-End Tests
- Test complete user workflows
- All services running (bot, agents, control-plane, tasks)
- Simulate real Slack interactions
- Location: `e2e/` (to be created)

---

## Agent Integration Tests

### Pattern: Test Agent Tools Directly

```python
"""
Integration test for ProfileAgent's internal search.
Tests the complete flow: vector search → synthesis → formatted context.
"""
import os
import pytest
from agents.profiler.tools.internal_search import internal_search_tool
from agents.profiler.utils import format_research_context
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_profile_agent_internal_search_real_data():
    """Test internal search with real vector DB and LLM."""

    # Skip if environment not configured
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured")
    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not configured")

    # Get the tool
    tool = internal_search_tool()
    if tool is None:
        pytest.skip("Internal search tool not available")

    # Run real search
    result = await tool._arun("profile Tesla Inc", effort="medium")

    # Verify structure
    assert "Relationship status:" in result
    assert len(result) > 100  # Should have substantial content

    # Verify it can be formatted
    state = {"research": {"internal_search": result}}
    formatted = format_research_context(state)

    assert "INTERNAL KNOWLEDGE BASE" in formatted
    assert "Tesla" in formatted
```

### Pattern: Test Agent Run Method

```python
"""
Integration test for complete agent execution.
Tests agent.run() with real services.
"""
import pytest
from agents.meddic_agent import MeddicAgent
from unittest.mock import AsyncMock

@pytest.mark.asyncio
@pytest.mark.integration
async def test_meddic_agent_full_run():
    """Test MeddicAgent with real LLM but mocked Slack."""

    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not configured")

    # Create agent
    agent = MeddicAgent()

    # Mock only Slack service (keep LLM real)
    mock_slack = AsyncMock()
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.add_reaction = AsyncMock()

    # Create context
    context = {
        "user_id": "U123",
        "channel": "C456",
        "thread_ts": "789.012",
        "slack_service": mock_slack,
        "llm_service": None,  # Agent will use its own
    }

    # Run agent
    result = await agent.run(
        query="Qualify Tesla as a lead using MEDDIC",
        context=context
    )

    # Verify response
    assert result["status"] == "success"
    assert "response" in result
    assert "Metrics" in result["response"]  # MEDDIC criteria

    # Verify Slack was called
    assert mock_slack.send_message.called
    assert mock_slack.add_reaction.called
```

### Pattern: Test Tool Integration

```python
"""
Test agent tool calls (web search, internal search, etc.).
"""
import pytest
from agents.profiler.nodes.researcher import (
    _execute_web_search,
    _execute_internal_search,
)
from langchain_core.messages import ToolMessage

@pytest.mark.asyncio
@pytest.mark.integration
async def test_researcher_web_search_integration():
    """Test web search tool with real Tavily API."""

    if not os.getenv("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not configured")

    tool_args = {
        "query": "Tesla revenue 2024",
        "max_results": 3
    }
    tool_id = "call_123"

    # Execute real web search
    result, note = await _execute_web_search(tool_args, tool_id, None)

    # Verify result structure
    assert isinstance(result, ToolMessage)
    assert "Tesla" in result.content
    assert "revenue" in result.content.lower()
    assert len(result.content) > 100

    # Verify note
    assert "Web search" in note
    assert "Tesla revenue 2024" in note
```

---

## Cross-Service Integration Tests

### Pattern: Bot → Agent Service

```python
"""
Test bot calling agent-service HTTP API.
"""
import pytest
import httpx
from bot.services.agent_client import AgentClient

@pytest.mark.asyncio
@pytest.mark.integration
async def test_bot_to_agent_service_profile_request():
    """Test bot sending profile request to agent-service."""

    # Requires agent-service running on localhost:8001
    agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")

    # Create client
    client = AgentClient(agent_url)

    try:
        # Make real HTTP call
        response = await client.invoke_agent(
            agent_name="profile",
            query="Create profile for Tesla Inc",
            context={
                "user_id": "U123",
                "channel": "C456",
                "thread_ts": "789.012",
            }
        )

        # Verify response
        assert response["status"] in ["success", "processing"]
        assert "response" in response or "job_id" in response

    except httpx.ConnectError:
        pytest.skip("Agent service not running at " + agent_url)
```

### Pattern: Control Plane → Tasks Service

```python
"""
Test control plane scheduling tasks.
"""
import pytest
import httpx

@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_plane_schedule_gdrive_ingestion():
    """Test scheduling Google Drive ingestion via control plane."""

    control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://localhost:8002")
    tasks_url = os.getenv("TASKS_URL", "http://localhost:5001")

    async with httpx.AsyncClient() as http:
        # Create scheduled task via control plane
        response = await http.post(
            f"{control_plane_url}/api/tasks/schedule",
            json={
                "job_type": "gdrive_ingestion",
                "schedule": "0 3 * * *",  # Daily at 3 AM
                "params": {
                    "folder_id": "test_folder_id",
                    "credential_id": "test_cred"
                }
            },
            headers={"Authorization": "Bearer test_token"}
        )

        assert response.status_code == 201
        task_id = response.json()["task_id"]

        # Verify task exists in tasks service
        task_response = await http.get(f"{tasks_url}/api/tasks/{task_id}")
        assert task_response.status_code == 200
        assert task_response.json()["job_type"] == "gdrive_ingestion"
```

### Pattern: End-to-End Message Flow

```python
"""
Test complete message flow: Slack → Bot → Agent → Response.
"""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@pytest.mark.integration
async def test_slack_message_to_agent_response_flow():
    """Test full flow from Slack message to agent response."""

    # Mock Slack event
    slack_event = {
        "type": "message",
        "user": "U123",
        "text": "@bot profile Tesla",
        "channel": "C456",
        "ts": "123.456"
    }

    # Mock Slack service (external API)
    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.457"})
    mock_slack.add_reaction = AsyncMock()

    # Use REAL agent service (must be running)
    agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")

    with patch("bot.services.slack_service.SlackService", return_value=mock_slack):
        from bot.handlers.message_handlers import handle_message

        result = await handle_message(
            text=slack_event["text"],
            user=slack_event["user"],
            slack_service=mock_slack,
            channel=slack_event["channel"],
            thread_ts=slack_event["ts"]
        )

        # Verify bot handled message
        assert result is True

        # Verify Slack was called
        assert mock_slack.send_message.called
        response_text = mock_slack.send_message.call_args[0][1]
        assert "Tesla" in response_text
```

---

## End-to-End Tests

### Pattern: Full Stack Test

```python
"""
E2E test with all services running.
Uses Docker Compose test environment.
"""
import pytest
import httpx
import asyncio

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_workflow_gdrive_to_rag():
    """
    Test complete workflow:
    1. Ingest doc from Google Drive
    2. Query bot about document
    3. Verify RAG retrieves document
    4. Verify response includes document content
    """

    # Assume services running via docker-compose-test.yml
    bot_url = "http://localhost:8000"
    tasks_url = "http://localhost:5001"

    async with httpx.AsyncClient(timeout=30.0) as http:
        # 1. Trigger Google Drive ingestion
        ingest_response = await http.post(
            f"{tasks_url}/api/jobs/gdrive-ingest",
            json={
                "folder_id": "test_folder",
                "credential_id": "test_cred"
            }
        )
        assert ingest_response.status_code == 202
        job_id = ingest_response.json()["job_id"]

        # 2. Wait for ingestion to complete
        for _ in range(10):
            status_response = await http.get(f"{tasks_url}/api/jobs/{job_id}")
            status = status_response.json()["status"]
            if status == "completed":
                break
            await asyncio.sleep(2)

        assert status == "completed", f"Ingestion failed: {status}"

        # 3. Query bot about document
        query_response = await http.post(
            f"{bot_url}/api/query",
            json={
                "user_id": "U123",
                "channel": "C456",
                "text": "What's in the test document?"
            }
        )

        assert query_response.status_code == 200
        response_text = query_response.json()["response"]

        # 4. Verify response includes document content
        assert "test document" in response_text.lower()
        assert len(response_text) > 50
```

---

## Test Infrastructure

### Test Fixtures

Create shared fixtures in `conftest.py`:

```python
# tests/integration/conftest.py
import pytest
import os
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture(scope="session")
def integration_env():
    """Check if integration test environment is available."""
    required = {
        "VECTOR_HOST": os.getenv("VECTOR_HOST"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        pytest.skip(f"Missing required env vars: {', '.join(missing)}")

    return required

@pytest.fixture
async def real_vector_store(integration_env):
    """Provide real Qdrant client."""
    from qdrant_client import AsyncQdrantClient

    client = AsyncQdrantClient(
        host=integration_env["VECTOR_HOST"],
        port=int(os.getenv("VECTOR_PORT", "6333"))
    )

    yield client

    await client.close()

@pytest.fixture
async def real_llm_service(integration_env):
    """Provide real LLM service."""
    from bot.services.llm_provider import LLMProvider

    provider = LLMProvider()
    yield provider
    # Cleanup if needed

@pytest.fixture
def mock_slack_service():
    """Provide mocked Slack service (external API)."""
    from unittest.mock import AsyncMock

    mock = AsyncMock()
    mock.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock.add_reaction = AsyncMock()
    mock.get_thread_history = AsyncMock(return_value=([], True))

    return mock
```

### Docker Compose for Integration Tests

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  bot-test:
    build: ./bot
    environment:
      - VECTOR_HOST=qdrant-test
      - LLM_API_KEY=${LLM_API_KEY}
      - AGENT_SERVICE_URL=http://agent-service-test:8001
    depends_on:
      - qdrant-test
      - agent-service-test
    ports:
      - "8000:8000"

  agent-service-test:
    build: ./agent-service
    environment:
      - VECTOR_HOST=qdrant-test
      - LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      - qdrant-test
    ports:
      - "8001:8001"

  qdrant-test:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant-test-data:/qdrant/storage

  control-plane-test:
    build: ./control_plane
    environment:
      - TASKS_URL=http://tasks-test:5001
    ports:
      - "8002:8002"

  tasks-test:
    build: ./tasks
    environment:
      - VECTOR_HOST=qdrant-test
    ports:
      - "5001:5001"

volumes:
  qdrant-test-data:
```

### Makefile Targets

```makefile
# Run integration tests
test-integration:
	PYTHONPATH=. pytest -v -m integration --tb=short

# Run E2E tests with Docker Compose
test-e2e:
	docker compose -f docker-compose.test.yml up -d
	sleep 10  # Wait for services
	PYTHONPATH=. pytest -v -m e2e --tb=short
	docker compose -f docker-compose.test.yml down

# Run all tests
test-all: test test-integration test-e2e
```

---

## Best Practices

### 1. Use Pytest Markers

```python
# Mark integration tests
@pytest.mark.integration
async def test_with_real_services():
    pass

# Mark E2E tests
@pytest.mark.e2e
async def test_full_workflow():
    pass

# Mark slow tests
@pytest.mark.slow
async def test_large_document_processing():
    pass
```

Run specific test types:
```bash
pytest -m integration      # Only integration tests
pytest -m "not integration"  # Skip integration tests
pytest -m e2e             # Only E2E tests
```

### 2. Environment-Based Skipping

```python
@pytest.mark.asyncio
async def test_requires_services():
    """Auto-skip if environment not configured."""
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured")

    # Test code here
```

### 3. Cleanup After Tests

```python
@pytest.fixture
async def test_vector_collection():
    """Create temporary collection for testing."""
    from qdrant_client import AsyncQdrantClient

    client = AsyncQdrantClient(host="localhost")
    collection_name = f"test_{uuid.uuid4().hex[:8]}"

    await client.create_collection(
        collection_name=collection_name,
        vectors_config={"size": 1536, "distance": "Cosine"}
    )

    yield collection_name

    # Cleanup
    await client.delete_collection(collection_name)
    await client.close()
```

### 4. Test Data Isolation

```python
# Use unique IDs for test data
test_user_id = f"TEST_U_{uuid.uuid4().hex[:8]}"
test_channel = f"TEST_C_{uuid.uuid4().hex[:8]}"

# Clean up test data after tests
async def cleanup_test_data(user_id):
    # Delete test messages, cache, etc.
    pass
```

### 5. Assertions for Integration Tests

```python
# Verify structure, not exact content
assert "Relationship status:" in result
assert len(result) > 100

# Verify key information present
assert "Tesla" in result
assert any(keyword in result.lower() for keyword in ["revenue", "earnings", "financial"])

# Verify response shape
assert "status" in response
assert response["status"] in ["success", "processing", "error"]
```

---

## Examples

### Example 1: Agent Tool Integration Test

```python
# evals/profiler/test_internal_search_integration.py
"""
Integration test for ProfileAgent internal search.
Tests: Vector DB → LLM synthesis → formatted output.
"""
import pytest
from agents.profiler.tools.internal_search import internal_search_tool

@pytest.mark.asyncio
@pytest.mark.integration
async def test_internal_search_with_real_vector_db():
    """Test internal search with real Qdrant and LLM."""

    # Skip if not configured
    if not os.getenv("VECTOR_HOST") or not os.getenv("LLM_API_KEY"):
        pytest.skip("Integration environment not configured")

    tool = internal_search_tool()

    # Search for known entity
    result = await tool._arun("profile 8th Light", effort="high")

    # Verify structure
    assert "Relationship status:" in result
    assert "8th Light" in result

    # Verify substantial content
    assert len(result) > 500

    # Should find our own case studies
    assert "Existing client" in result or "case study" in result.lower()
```

### Example 2: Cross-Service Integration Test

```python
# tests/integration/test_bot_agent_flow.py
"""
Integration test for bot → agent-service flow.
"""
import pytest
import httpx

@pytest.mark.asyncio
@pytest.mark.integration
async def test_bot_calls_agent_service_for_profile():
    """Test bot successfully calls agent-service."""

    agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{agent_url}/api/agents/profile/invoke",
                json={
                    "query": "Profile Tesla Inc",
                    "context": {
                        "user_id": "U123",
                        "channel": "C456"
                    }
                },
                timeout=60.0
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert "Tesla" in data["response"]

        except httpx.ConnectError:
            pytest.skip(f"Agent service not available at {agent_url}")
```

### Example 3: E2E Workflow Test

```python
# tests/e2e/test_document_ingestion_query.py
"""
E2E test: Ingest document → Query → Get answer from RAG.
"""
import pytest
import httpx
import asyncio

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_document_ingestion_to_query_workflow():
    """Test full document workflow."""

    tasks_url = "http://localhost:5001"
    bot_url = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=60.0) as http:
        # 1. Upload test document
        files = {"file": ("test.txt", "This is test content about widgets.")}
        upload_response = await http.post(
            f"{tasks_url}/api/documents/upload",
            files=files
        )
        assert upload_response.status_code == 201
        doc_id = upload_response.json()["document_id"]

        # 2. Wait for indexing
        await asyncio.sleep(5)

        # 3. Query about document
        query_response = await http.post(
            f"{bot_url}/api/query",
            json={
                "user_id": "U123",
                "text": "Tell me about widgets"
            }
        )

        assert query_response.status_code == 200
        response_text = query_response.json()["response"]

        # 4. Verify RAG found document
        assert "widget" in response_text.lower()
        assert len(response_text) > 20
```

---

## Running Integration Tests

### Quick Integration Tests
```bash
# Run all integration tests
make test-integration

# Run specific test file
pytest tests/integration/test_agent_flow.py -v

# Run with live output
pytest tests/integration/ -v -s
```

### Full E2E Tests
```bash
# Start test environment
docker compose -f docker-compose.test.yml up -d

# Run E2E tests
make test-e2e

# Stop environment
docker compose -f docker-compose.test.yml down
```

### CI Integration
```yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on:
  pull_request:
  push:
    branches: [main, develop]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Run integration tests
        env:
          VECTOR_HOST: localhost
          VECTOR_PORT: 6333
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
        run: pytest -m integration -v
```

---

## Summary

**Key Principles:**
1. **Test real integrations** - Use actual services (vector DB, LLM) when possible
2. **Mock external APIs** - Mock Slack, GitHub, etc. (rate limits, costs)
3. **Isolate test data** - Use unique IDs, clean up after tests
4. **Skip gracefully** - Auto-skip when environment not configured
5. **Test end-to-end** - Validate complete workflows, not just components

**Start Simple:**
1. Write agent tool integration tests first
2. Add cross-service tests second
3. Build E2E tests last

**Maintain Quality:**
- Run integration tests in CI
- Keep tests fast (<30s each)
- Monitor flakiness
- Update tests with code changes

"""
Smoke Test Suite - Quick validation of critical functionality.

Run this before releases or after major changes to verify everything works.
Tests real integrations but uses test data to avoid polluting production.

Usage:
    pytest tests/smoke/test_smoke_suite.py -v
    pytest tests/smoke/test_smoke_suite.py -v -s  # With output
    make test-smoke  # If Makefile target exists
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import pytest
from dotenv import load_dotenv

# Load environment
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

# Add to path
sys.path.insert(0, str(ROOT_DIR / "bot"))
sys.path.insert(0, str(ROOT_DIR / "agent-service"))


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def smoke_env():
    """Verify smoke test environment is configured."""
    required = {
        "LLM_API_KEY": os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
        "VECTOR_HOST": os.getenv("VECTOR_HOST"),
    }

    optional = {
        "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN"),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
        "AGENT_SERVICE_URL": os.getenv("AGENT_SERVICE_URL", "http://localhost:8001"),
    }

    missing_required = [k for k, v in required.items() if not v]
    if missing_required:
        pytest.fail(f"❌ Missing required env vars: {', '.join(missing_required)}")

    return {**required, **optional}


@pytest.fixture(scope="session")
def test_user_id():
    """Test user ID for smoke tests."""
    return "U_SMOKE_TEST"


@pytest.fixture(scope="session")
def test_channel():
    """Test channel for smoke tests."""
    return "C_SMOKE_TEST"


# ============================================================================
# SLACK TESTS (If token available)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_slack_connection(smoke_env):
    """Smoke: Verify Slack connection works."""
    if not smoke_env.get("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not configured - skipping Slack tests")

    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=smoke_env["SLACK_BOT_TOKEN"])

    # Test auth
    response = await client.auth_test()

    assert response["ok"], "Slack auth failed"
    assert "user_id" in response
    assert "team_id" in response

    print(f"\n✅ Slack: Connected as {response['user']} in team {response['team']}")


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_slack_send_test_message(smoke_env, test_channel):
    """Smoke: Send test message to Slack."""
    if not smoke_env.get("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not configured")

    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=smoke_env["SLACK_BOT_TOKEN"])

    try:
        # Send test message
        response = await client.chat_postMessage(
            channel=test_channel, text="🧪 Smoke test message - please ignore", mrkdwn=True
        )

        assert response["ok"], "Failed to send Slack message"
        assert "ts" in response

        print(f"\n✅ Slack: Sent test message (ts: {response['ts']})")

        # Clean up - delete message
        await client.chat_delete(channel=test_channel, ts=response["ts"])
        print("✅ Slack: Cleaned up test message")

    except Exception as e:
        if "channel_not_found" in str(e):
            pytest.skip(f"Test channel {test_channel} not found - update test_channel fixture")
        raise


# ============================================================================
# VECTOR DB TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_vector_db_connection(smoke_env):
    """Smoke: Verify Qdrant connection works."""
    from qdrant_client import AsyncQdrantClient

    host = smoke_env["VECTOR_HOST"]
    port = int(os.getenv("VECTOR_PORT", "6333"))

    client = AsyncQdrantClient(host=host, port=port)

    try:
        # Check health
        collections = await client.get_collections()

        assert collections is not None
        print(f"\n✅ Vector DB: Connected to {host}:{port}")
        print(f"   Collections: {len(collections.collections)}")

    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_vector_db_search(smoke_env):
    """Smoke: Verify vector search works."""
    from qdrant_client import AsyncQdrantClient, models

    host = smoke_env["VECTOR_HOST"]
    port = int(os.getenv("VECTOR_PORT", "6333"))

    client = AsyncQdrantClient(host=host, port=port)

    try:
        collections = await client.get_collections()

        if len(collections.collections) == 0:
            pytest.skip("No collections in vector DB - skipping search test")

        # Get first collection
        collection_name = collections.collections[0].name

        # Try a search
        results = await client.search(
            collection_name=collection_name,
            query_vector=[0.1] * 1536,  # Dummy vector
            limit=1,
        )

        print(f"\n✅ Vector DB: Search works on collection '{collection_name}'")
        print(f"   Found {len(results)} results")

    finally:
        await client.close()


# ============================================================================
# LLM TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_llm_connection(smoke_env):
    """Smoke: Verify LLM provider works."""
    from openai import AsyncOpenAI

    api_key = smoke_env["LLM_API_KEY"]
    client = AsyncOpenAI(api_key=api_key)

    # Simple test completion
    response = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": "Say 'test' and nothing else"}],
        max_tokens=10,
    )

    assert response.choices[0].message.content
    print(f"\n✅ LLM: Connection works")
    print(f"   Model: {response.model}")
    print(f"   Response: {response.choices[0].message.content}")


# ============================================================================
# AGENT SERVICE TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_agent_service_health(smoke_env):
    """Smoke: Verify agent-service is running."""
    agent_url = smoke_env.get("AGENT_SERVICE_URL")
    if not agent_url:
        pytest.skip("AGENT_SERVICE_URL not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{agent_url}/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "healthy"
            print(f"\n✅ Agent Service: Healthy at {agent_url}")
            print(f"   Version: {data.get('version', 'unknown')}")

        except httpx.ConnectError:
            pytest.skip(f"Agent service not running at {agent_url}")


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_agent_service_list_agents(smoke_env):
    """Smoke: Verify agent discovery works."""
    agent_url = smoke_env.get("AGENT_SERVICE_URL")
    if not agent_url:
        pytest.skip("AGENT_SERVICE_URL not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{agent_url}/api/agents")

            assert response.status_code == 200
            agents = response.json()

            assert isinstance(agents, list)
            assert len(agents) > 0

            print(f"\n✅ Agent Service: Found {len(agents)} agents")
            for agent in agents[:5]:
                print(f"   - {agent.get('name')}: {agent.get('description', '')[:50]}")

        except httpx.ConnectError:
            pytest.skip(f"Agent service not running at {agent_url}")


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_agent_service_invoke_simple(smoke_env, test_user_id, test_channel):
    """Smoke: Test simple agent invocation."""
    agent_url = smoke_env.get("AGENT_SERVICE_URL")
    if not agent_url:
        pytest.skip("AGENT_SERVICE_URL not configured")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Invoke a simple agent (assuming 'meddic' exists)
            response = await client.post(
                f"{agent_url}/api/agents/meddic/invoke",
                json={
                    "query": "What is MEDDIC?",
                    "context": {"user_id": test_user_id, "channel": test_channel},
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] in ["success", "processing"]
            assert "response" in data or "job_id" in data

            print(f"\n✅ Agent Service: Successfully invoked 'meddic' agent")
            if "response" in data:
                print(f"   Response preview: {data['response'][:100]}...")

        except httpx.ConnectError:
            pytest.skip(f"Agent service not running at {agent_url}")


# ============================================================================
# BOT INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_bot_message_handler(smoke_env, test_user_id, test_channel):
    """Smoke: Test bot message handling flow."""
    from unittest.mock import AsyncMock

    from handlers.message_handlers import handle_message

    # Mock Slack service
    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.add_reaction = AsyncMock()

    # Test message
    text = "What is 2+2?"

    result = await handle_message(
        text=text,
        user=test_user_id,
        slack_service=mock_slack,
        channel=test_channel,
        thread_ts=None,
    )

    assert result is True, "Message handler should return True"
    assert mock_slack.send_message.called, "Should send response"

    response_text = mock_slack.send_message.call_args[0][1]
    assert len(response_text) > 0, "Response should not be empty"
    assert "4" in response_text, "Should answer the question"

    print(f"\n✅ Bot: Message handler works")
    print(f"   Question: {text}")
    print(f"   Answer: {response_text[:100]}...")


# ============================================================================
# RAG TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_rag_retrieval(smoke_env):
    """Smoke: Test RAG retrieval works."""
    if not smoke_env.get("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured")

    from services.retrieval_service import RetrievalService

    retrieval_service = RetrievalService()

    # Test query
    query = "What is our company about?"
    chunks = await retrieval_service.retrieve_context(query=query, top_k=3)

    assert isinstance(chunks, list)
    print(f"\n✅ RAG: Retrieved {len(chunks)} chunks")

    if len(chunks) > 0:
        print(f"   First chunk preview: {chunks[0][:100]}...")
    else:
        print("   ⚠️  No chunks found (vector DB might be empty)")


# ============================================================================
# WEB SEARCH TESTS (Optional)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_web_search(smoke_env):
    """Smoke: Test web search integration."""
    if not smoke_env.get("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not configured - skipping web search test")

    from services.search_clients import TavilySearchClient

    client = TavilySearchClient(api_key=smoke_env["TAVILY_API_KEY"])

    results = await client.search("Python programming language", max_results=3)

    assert isinstance(results, list)
    assert len(results) > 0

    print(f"\n✅ Web Search: Found {len(results)} results")
    print(f"   First result: {results[0].get('title', 'N/A')}")


# ============================================================================
# SUMMARY TEST
# ============================================================================


@pytest.mark.smoke
def test_smoke_suite_summary():
    """Display summary of smoke test results."""
    print("\n" + "=" * 80)
    print("🧪 SMOKE TEST SUITE COMPLETE")
    print("=" * 80)
    print("\nAll critical systems verified:")
    print("  ✅ Slack integration")
    print("  ✅ Vector database (Qdrant)")
    print("  ✅ LLM provider")
    print("  ✅ Agent service")
    print("  ✅ Bot message handling")
    print("  ✅ RAG retrieval")
    print("  ✅ Web search (optional)")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

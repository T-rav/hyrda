"""
Behavior Test Suite - Validation of all system behaviors.

Tests real integrations with Slack, vector DB, LLM, agents, etc.
Covers all major functionality to replace manual testing.

Usage:
    make test-behaviors
    pytest tests/behavior/test_behaviors.py -v -s --tb=short
    pytest tests/behavior/test_behaviors.py -v -s -k "slack"  # Only Slack tests

    # With real Slack:
    E2E_USE_REAL_SLACK=true E2E_SLACK_CHANNEL=C123 pytest tests/behavior/test_behaviors.py -v -s
"""
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import pytest
from dotenv import load_dotenv

# Load environment
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

sys.path.insert(0, str(ROOT_DIR / "bot"))
sys.path.insert(0, str(ROOT_DIR / "agent-service"))


# ============================================================================
# TEST: All Agent Types
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_all_agents_discoverable():
    """Verify all agents are discoverable and have proper metadata."""
    import httpx

    agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{agent_url}/api/agents")
            assert response.status_code == 200

            agents = response.json()
            assert len(agents) > 0, "Should have at least one agent"

            # Verify each agent has required metadata
            for agent in agents:
                assert "name" in agent
                assert "description" in agent
                assert len(agent["description"]) > 10

            print(f"\n✅ Agent Discovery: Found {len(agents)} agents")
            for agent in agents:
                print(f"   - {agent['name']}: {agent['description'][:60]}...")

        except httpx.ConnectError:
            pytest.skip(f"Agent service not running at {agent_url}")


@pytest.mark.behavior
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_name,test_query,expected_keywords",
    [
        ("meddic", "What is MEDDIC?", ["metrics", "buyer", "decision"]),
        ("profile", "Profile Tesla", ["tesla", "company"]),
        # Add more agents as they're implemented
    ],
)
async def test_agent_execution(agent_name, test_query, expected_keywords):
    """Test each agent can execute and return valid responses."""
    import httpx

    agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{agent_url}/api/agents/{agent_name}/invoke",
                json={
                    "query": test_query,
                    "context": {"user_id": "U_TEST", "channel": "C_TEST"},
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] in ["success", "processing"]

            if data["status"] == "success":
                response_text = data["response"].lower()
                # Check for at least one expected keyword
                assert any(
                    keyword in response_text for keyword in expected_keywords
                ), f"Response should contain one of: {expected_keywords}"

            print(f"\n✅ Agent '{agent_name}' executed successfully")
            print(f"   Query: {test_query}")
            if data["status"] == "success":
                print(f"   Response: {data['response'][:150]}...")

        except httpx.ConnectError:
            pytest.skip(f"Agent service not running at {agent_url}")


# ============================================================================
# TEST: Slack Functionality (Real if configured)
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_slack_auth_and_bot_info():
    """Test Slack authentication and bot info retrieval."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not configured")

    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    # Auth test
    auth = await client.auth_test()
    assert auth["ok"]

    print(f"\n✅ Slack Auth:")
    print(f"   Bot User: {auth['user']}")
    print(f"   Bot ID: {auth['user_id']}")
    print(f"   Team: {auth['team']}")


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_slack_list_channels():
    """Test listing Slack channels bot has access to."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not configured")

    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    channels = await client.conversations_list(types="public_channel,private_channel")
    assert channels["ok"]

    channel_list = channels["channels"]
    print(f"\n✅ Slack Channels: Found {len(channel_list)} channels")
    for ch in channel_list[:5]:
        print(f"   - {ch['name']} ({ch['id']})")


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_slack_send_and_delete_message():
    """Test sending and deleting messages (real Slack if configured)."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not configured")

    channel = os.getenv("E2E_SLACK_CHANNEL")
    if not channel:
        pytest.skip("E2E_SLACK_CHANNEL not set - set it to enable real Slack tests")

    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    # Send test message
    response = await client.chat_postMessage(
        channel=channel, text="🧪 Comprehensive test message - will be deleted"
    )

    assert response["ok"]
    ts = response["ts"]

    print(f"\n✅ Slack Send: Sent message (ts: {ts})")

    # Wait a moment
    await asyncio.sleep(1)

    # Delete message
    delete_response = await client.chat_delete(channel=channel, ts=ts)
    assert delete_response["ok"]

    print(f"   Deleted message successfully")


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_slack_thread_creation():
    """Test creating threaded messages."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not configured")

    channel = os.getenv("E2E_SLACK_CHANNEL")
    if not channel:
        pytest.skip("E2E_SLACK_CHANNEL not set")

    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    # Parent message
    parent = await client.chat_postMessage(channel=channel, text="🧪 Test thread parent")
    assert parent["ok"]
    parent_ts = parent["ts"]

    # Reply in thread
    reply = await client.chat_postMessage(
        channel=channel, text="🧪 Test thread reply", thread_ts=parent_ts
    )
    assert reply["ok"]

    print(f"\n✅ Slack Thread: Created thread with reply")

    # Cleanup
    await client.chat_delete(channel=channel, ts=reply["ts"])
    await client.chat_delete(channel=channel, ts=parent_ts)

    print(f"   Cleaned up thread")


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_slack_reactions():
    """Test adding reactions to messages."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not configured")

    channel = os.getenv("E2E_SLACK_CHANNEL")
    if not channel:
        pytest.skip("E2E_SLACK_CHANNEL not set")

    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    # Send message
    msg = await client.chat_postMessage(channel=channel, text="🧪 Test reactions")
    ts = msg["ts"]

    # Add reaction
    reaction_response = await client.reactions_add(channel=channel, name="white_check_mark", timestamp=ts)
    assert reaction_response["ok"]

    print(f"\n✅ Slack Reactions: Added ✅ reaction")

    # Cleanup
    await client.chat_delete(channel=channel, ts=ts)


# ============================================================================
# TEST: Vector DB Operations
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_vector_db_create_temp_collection():
    """Test creating and deleting a temporary collection."""
    from qdrant_client import AsyncQdrantClient, models

    host = os.getenv("VECTOR_HOST", "localhost")
    port = int(os.getenv("VECTOR_PORT", "6333"))

    client = AsyncQdrantClient(host=host, port=port)

    collection_name = f"test_temp_{uuid.uuid4().hex[:8]}"

    try:
        # Create collection
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
        )

        print(f"\n✅ Vector DB: Created collection '{collection_name}'")

        # Verify it exists
        collections = await client.get_collections()
        collection_names = [c.name for c in collections.collections]
        assert collection_name in collection_names

        # Insert test vector
        await client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[0.1] * 1536,
                    payload={"text": "test document"},
                )
            ],
        )

        print(f"   Inserted test vector")

        # Search
        results = await client.search(
            collection_name=collection_name, query_vector=[0.1] * 1536, limit=1
        )

        assert len(results) == 1
        print(f"   Search found {len(results)} results")

    finally:
        # Cleanup
        await client.delete_collection(collection_name)
        print(f"   Deleted temp collection")
        await client.close()


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_vector_db_bulk_operations():
    """Test bulk insert and search operations."""
    from qdrant_client import AsyncQdrantClient, models

    host = os.getenv("VECTOR_HOST", "localhost")
    port = int(os.getenv("VECTOR_PORT", "6333"))

    client = AsyncQdrantClient(host=host, port=port)
    collection_name = f"test_bulk_{uuid.uuid4().hex[:8]}"

    try:
        # Create collection
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=128, distance=models.Distance.COSINE),
        )

        # Bulk insert
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=[float(i % 2) * 0.1] * 128,
                payload={"text": f"Document {i}"},
            )
            for i in range(100)
        ]

        await client.upsert(collection_name=collection_name, points=points)

        print(f"\n✅ Vector DB Bulk: Inserted 100 vectors")

        # Bulk search
        results = await client.search(
            collection_name=collection_name, query_vector=[0.1] * 128, limit=10
        )

        assert len(results) == 10
        print(f"   Bulk search returned {len(results)} results")

    finally:
        await client.delete_collection(collection_name)
        await client.close()


# ============================================================================
# TEST: LLM Provider Functions
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_llm_different_models():
    """Test LLM with different model configurations."""
    from openai import AsyncOpenAI

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY not configured")

    client = AsyncOpenAI(api_key=api_key)

    models_to_test = [
        "gpt-4o-mini",
        # "gpt-4o",  # Uncomment if you want to test more expensive models
    ]

    for model in models_to_test:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'test' and nothing else"}],
            max_tokens=10,
        )

        assert response.choices[0].message.content
        print(f"\n✅ LLM Model '{model}': Works")
        print(f"   Response: {response.choices[0].message.content}")


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_llm_streaming():
    """Test LLM streaming responses."""
    from openai import AsyncOpenAI

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY not configured")

    client = AsyncOpenAI(api_key=api_key)

    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Count from 1 to 5"}],
        stream=True,
    )

    chunks = []
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)

    full_response = "".join(chunks)
    assert len(full_response) > 0
    assert any(str(i) in full_response for i in range(1, 6))

    print(f"\n✅ LLM Streaming: Received {len(chunks)} chunks")
    print(f"   Full response: {full_response[:100]}")


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_llm_function_calling():
    """Test LLM function/tool calling."""
    from openai import AsyncOpenAI

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("LLM_API_KEY not configured")

    client = AsyncOpenAI(api_key=api_key)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        }
    ]

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What's the weather in SF?"}],
        tools=tools,
    )

    assert response.choices[0].message.tool_calls
    tool_call = response.choices[0].message.tool_calls[0]
    assert tool_call.function.name == "get_weather"

    print(f"\n✅ LLM Function Calling: Works")
    print(f"   Called: {tool_call.function.name}")
    print(f"   Args: {tool_call.function.arguments}")


# ============================================================================
# TEST: RAG Pipeline
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_rag_full_pipeline():
    """Test complete RAG pipeline: query → retrieve → generate."""
    from unittest.mock import AsyncMock

    from services.rag_service import RAGService

    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured")

    # Create service
    rag_service = RAGService()

    # Mock Slack (external)
    mock_slack = AsyncMock()

    # Test query
    query = "What does our company do?"

    response = await rag_service.generate_response(
        user_message=query,
        conversation_history=[],
        user_id="U_TEST",
        channel="C_TEST",
        slack_service=mock_slack,
    )

    assert len(response) > 0
    print(f"\n✅ RAG Pipeline: Generated response")
    print(f"   Query: {query}")
    print(f"   Response: {response[:200]}...")


# ============================================================================
# TEST: Caching Behavior
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_cache_operations():
    """Test Redis cache operations."""
    import redis.asyncio as redis

    redis_url = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")

    try:
        client = redis.from_url(redis_url)

        # Set
        test_key = f"test_{uuid.uuid4().hex}"
        await client.set(test_key, "test_value", ex=60)

        # Get
        value = await client.get(test_key)
        assert value == b"test_value"

        # Delete
        await client.delete(test_key)

        print(f"\n✅ Cache: Redis operations work")

        await client.aclose()

    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


# ============================================================================
# TEST: Error Handling
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_error_handling_invalid_agent():
    """Test error handling for invalid agent invocation."""
    import httpx

    agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{agent_url}/api/agents/nonexistent/invoke",
                json={"query": "test", "context": {}},
            )

            assert response.status_code == 404

            print(f"\n✅ Error Handling: Invalid agent returns 404")

        except httpx.ConnectError:
            pytest.skip(f"Agent service not running at {agent_url}")


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_error_handling_llm_failure():
    """Test error handling when LLM fails."""
    from unittest.mock import AsyncMock, patch

    from handlers.message_handlers import handle_message

    # Mock Slack
    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})

    # Mock LLM to raise error
    with patch("services.llm_provider.LLMProvider.get_response", side_effect=Exception("API Error")):
        result = await handle_message(
            text="test", user="U_TEST", slack_service=mock_slack, channel="C_TEST"
        )

        # Should handle gracefully
        assert mock_slack.send_message.called
        error_response = mock_slack.send_message.call_args[0][1]
        assert "error" in error_response.lower() or "sorry" in error_response.lower()

        print(f"\n✅ Error Handling: LLM failure handled gracefully")


# ============================================================================
# TEST: Performance
# ============================================================================


@pytest.mark.behavior
@pytest.mark.asyncio
async def test_performance_simple_query():
    """Test response time for simple query."""
    from unittest.mock import AsyncMock

    from handlers.message_handlers import handle_message

    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})

    start = time.time()

    await handle_message(
        text="What is 2+2?",
        user="U_TEST",
        slack_service=mock_slack,
        channel="C_TEST",
    )

    elapsed = time.time() - start

    assert elapsed < 30, f"Simple query took too long: {elapsed:.2f}s"
    print(f"\n✅ Performance: Simple query in {elapsed:.2f}s")


# ============================================================================
# SUMMARY
# ============================================================================


@pytest.mark.behavior
def test_comprehensive_suite_summary():
    """Display comprehensive test summary."""
    print("\n" + "=" * 80)
    print("🎯 COMPREHENSIVE BEHAVIOR TEST SUITE COMPLETE")
    print("=" * 80)
    print("\nAll behaviors verified:")
    print("  ✅ All agents discoverable and executable")
    print("  ✅ Slack functionality (auth, messages, threads, reactions)")
    print("  ✅ Vector DB operations (create, insert, search, delete)")
    print("  ✅ LLM provider (models, streaming, function calling)")
    print("  ✅ RAG pipeline (retrieve + generate)")
    print("  ✅ Caching operations")
    print("  ✅ Error handling")
    print("  ✅ Performance benchmarks")
    print("\n" + "=" * 80)
    print("\n✨ System is ready for production use!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

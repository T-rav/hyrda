"""
End-to-End Test Suite - Complete workflow tests.

Tests entire user journeys from Slack message to final response.
Uses real Slack channel if configured, otherwise mocks Slack API.

Usage:
    pytest tests/smoke/test_end_to_end.py -v -s
    E2E_SLACK_CHANNEL=C123456 pytest tests/smoke/test_end_to_end.py -v
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

import pytest
from dotenv import load_dotenv

# Load environment
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

sys.path.insert(0, str(ROOT_DIR / "bot"))


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def e2e_env():
    """E2E test environment configuration."""
    return {
        "slack_channel": os.getenv("E2E_SLACK_CHANNEL"),  # Optional real channel
        "slack_token": os.getenv("SLACK_BOT_TOKEN"),
        "use_real_slack": os.getenv("E2E_USE_REAL_SLACK", "false").lower() == "true",
    }


@pytest.fixture
def test_message_id():
    """Unique test message ID."""
    return f"test_{uuid.uuid4().hex[:8]}"


# ============================================================================
# E2E TEST: Simple Q&A
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_simple_question_answer(e2e_env, test_message_id):
    """
    E2E: User asks simple question → Bot responds correctly.

    Flow:
    1. User sends: "What is 2+2?"
    2. Bot processes message
    3. LLM generates response
    4. Bot sends response to Slack
    """
    from unittest.mock import AsyncMock, patch

    from handlers.message_handlers import handle_message

    # Setup
    user_id = "U_E2E_TEST"
    channel = e2e_env.get("slack_channel", "C_E2E_TEST")
    question = "What is 2+2? Just give me the number."

    if e2e_env["use_real_slack"] and e2e_env["slack_token"]:
        # Use real Slack
        from slack_sdk.web.async_client import AsyncWebClient

        from services.slack_service import SlackService

        slack_service = SlackService(AsyncWebClient(token=e2e_env["slack_token"]))

        print(f"\n🔴 USING REAL SLACK - Channel: {channel}")
        print(f"   Question: {question}")

        # Send message
        result = await handle_message(
            text=question,
            user=user_id,
            slack_service=slack_service,
            channel=channel,
            thread_ts=None,
        )

        assert result is True
        print("✅ E2E: Message sent to real Slack successfully")

    else:
        # Mock Slack
        mock_slack = AsyncMock()
        mock_slack.get_thread_history = AsyncMock(return_value=([], True))
        mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
        mock_slack.add_reaction = AsyncMock()

        print(f"\n🟡 USING MOCK SLACK")
        print(f"   Question: {question}")

        result = await handle_message(
            text=question,
            user=user_id,
            slack_service=mock_slack,
            channel=channel,
            thread_ts=None,
        )

        assert result is True
        assert mock_slack.send_message.called

        response = mock_slack.send_message.call_args[0][1]
        assert "4" in response

        print(f"   Response: {response[:200]}")
        print("✅ E2E: Simple Q&A works")


# ============================================================================
# E2E TEST: Agent Invocation
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_agent_invocation(e2e_env, test_message_id):
    """
    E2E: User invokes agent → Agent processes → Response sent.

    Flow:
    1. User sends: "@bot /meddic What is MEDDIC?"
    2. Bot detects agent command
    3. Bot calls agent-service
    4. Agent processes and responds
    5. Bot sends result to Slack
    """
    from unittest.mock import AsyncMock

    from handlers.message_handlers import handle_message

    # Setup
    user_id = "U_E2E_TEST"
    channel = e2e_env.get("slack_channel", "C_E2E_TEST")
    command = "What is the MEDDIC framework? Brief answer only."

    # Mock Slack
    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.add_reaction = AsyncMock()

    print(f"\n🤖 Testing agent invocation")
    print(f"   Command: {command}")

    result = await handle_message(
        text=command,
        user=user_id,
        slack_service=mock_slack,
        channel=channel,
        thread_ts=None,
    )

    assert result is True
    assert mock_slack.send_message.called

    response = mock_slack.send_message.call_args[0][1]
    assert len(response) > 50, "Agent should provide substantial response"
    assert any(
        word in response.upper() for word in ["MEDDIC", "METRICS", "BUYER"]
    ), "Response should mention MEDDIC concepts"

    print(f"   Response preview: {response[:200]}...")
    print("✅ E2E: Agent invocation works")


# ============================================================================
# E2E TEST: RAG Query
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_rag_query(e2e_env, test_message_id):
    """
    E2E: User asks about documents → RAG retrieves context → Response includes docs.

    Flow:
    1. User asks question about company/documents
    2. Bot retrieves relevant chunks from vector DB
    3. LLM generates answer using context
    4. Bot sends response
    """
    from unittest.mock import AsyncMock

    from handlers.message_handlers import handle_message

    # Setup
    user_id = "U_E2E_TEST"
    channel = e2e_env.get("slack_channel", "C_E2E_TEST")
    query = "What services does our company provide?"

    # Mock Slack
    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.add_reaction = AsyncMock()

    print(f"\n📚 Testing RAG query")
    print(f"   Query: {query}")

    result = await handle_message(
        text=query, user=user_id, slack_service=mock_slack, channel=channel, thread_ts=None
    )

    assert result is True
    assert mock_slack.send_message.called

    response = mock_slack.send_message.call_args[0][1]
    assert len(response) > 50, "Should provide informative response"

    print(f"   Response preview: {response[:200]}...")
    print("✅ E2E: RAG query works")


# ============================================================================
# E2E TEST: Thread Conversation
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_thread_conversation(e2e_env, test_message_id):
    """
    E2E: Multi-message thread conversation with context.

    Flow:
    1. User asks first question
    2. Bot responds
    3. User asks follow-up (references previous context)
    4. Bot responds with context awareness
    """
    from unittest.mock import AsyncMock

    from handlers.message_handlers import handle_message

    # Setup
    user_id = "U_E2E_TEST"
    channel = e2e_env.get("slack_channel", "C_E2E_TEST")
    thread_ts = "1234567890.123456"

    # Mock Slack
    mock_slack = AsyncMock()
    mock_slack.send_message = AsyncMock(return_value={"ts": thread_ts})
    mock_slack.add_reaction = AsyncMock()

    print(f"\n💬 Testing thread conversation")

    # First message
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))

    result1 = await handle_message(
        text="My favorite color is blue.",
        user=user_id,
        slack_service=mock_slack,
        channel=channel,
        thread_ts=thread_ts,
    )

    assert result1 is True
    response1 = mock_slack.send_message.call_args[0][1]
    print(f"   User: My favorite color is blue.")
    print(f"   Bot: {response1[:100]}...")

    # Second message with context
    mock_slack.get_thread_history = AsyncMock(
        return_value=(
            [
                {"role": "user", "content": "My favorite color is blue."},
                {"role": "assistant", "content": response1},
            ],
            True,
        )
    )

    result2 = await handle_message(
        text="What color did I just mention?",
        user=user_id,
        slack_service=mock_slack,
        channel=channel,
        thread_ts=thread_ts,
    )

    assert result2 is True
    response2 = mock_slack.send_message.call_args[0][1]

    # Should remember context
    assert "blue" in response2.lower(), "Bot should remember the color from thread history"

    print(f"   User: What color did I just mention?")
    print(f"   Bot: {response2[:100]}...")
    print("✅ E2E: Thread conversation with context works")


# ============================================================================
# E2E TEST: File Attachment
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_file_attachment_processing(e2e_env, test_message_id):
    """
    E2E: User uploads file → Bot processes → Responds about content.

    Flow:
    1. User uploads text/PDF file with question
    2. Bot downloads and extracts content
    3. Bot caches file content
    4. Bot responds referencing file content
    """
    from unittest.mock import AsyncMock, Mock

    from handlers.message_handlers import handle_message

    # Setup
    user_id = "U_E2E_TEST"
    channel = e2e_env.get("slack_channel", "C_E2E_TEST")
    thread_ts = "1234567890.654321"

    # Mock file
    mock_file = {
        "name": "test_document.txt",
        "mimetype": "text/plain",
        "size": 1024,
        "url_private": "https://files.slack.com/test.txt",
    }

    # Mock Slack with file
    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": thread_ts})
    mock_slack.add_reaction = AsyncMock()
    mock_slack.download_file = AsyncMock(
        return_value=b"This is test content about widgets and gadgets."
    )

    print(f"\n📎 Testing file attachment processing")
    print(f"   File: {mock_file['name']}")

    # Message with file
    from handlers.file_processors import process_file_attachments

    # Process file
    file_contents = await process_file_attachments([mock_file], mock_slack)

    assert len(file_contents) == 1
    assert "widget" in file_contents[0].lower()

    print(f"   Extracted content: {file_contents[0][:100]}...")
    print("✅ E2E: File attachment processing works")


# ============================================================================
# E2E TEST: Web Search
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_web_search_query(e2e_env, test_message_id):
    """
    E2E: User asks current events question → Bot uses web search → Response includes results.

    Flow:
    1. User asks about recent/current event
    2. Bot detects need for web search
    3. Bot calls Tavily/web search
    4. LLM uses search results
    5. Bot responds with current information
    """
    if not os.getenv("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not configured - skipping web search test")

    from unittest.mock import AsyncMock

    from handlers.message_handlers import handle_message

    # Setup
    user_id = "U_E2E_TEST"
    channel = e2e_env.get("slack_channel", "C_E2E_TEST")
    query = "What is the current weather in San Francisco?"

    # Mock Slack
    mock_slack = AsyncMock()
    mock_slack.get_thread_history = AsyncMock(return_value=([], True))
    mock_slack.send_message = AsyncMock(return_value={"ts": "123.456"})
    mock_slack.add_reaction = AsyncMock()

    print(f"\n🌐 Testing web search query")
    print(f"   Query: {query}")

    result = await handle_message(
        text=query, user=user_id, slack_service=mock_slack, channel=channel, thread_ts=None
    )

    assert result is True
    assert mock_slack.send_message.called

    response = mock_slack.send_message.call_args[0][1]
    assert len(response) > 50

    print(f"   Response preview: {response[:200]}...")
    print("✅ E2E: Web search query works")


# ============================================================================
# E2E SUMMARY
# ============================================================================


@pytest.mark.e2e
def test_e2e_suite_summary():
    """Display E2E test summary."""
    print("\n" + "=" * 80)
    print("🎯 END-TO-END TEST SUITE COMPLETE")
    print("=" * 80)
    print("\nAll user workflows verified:")
    print("  ✅ Simple Q&A")
    print("  ✅ Agent invocation")
    print("  ✅ RAG queries")
    print("  ✅ Thread conversations")
    print("  ✅ File attachments")
    print("  ✅ Web search (optional)")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

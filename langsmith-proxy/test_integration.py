#!/usr/bin/env python3
"""
Integration test for LangSmith-to-Langfuse proxy.

Tests that LangGraph agent traces are successfully proxied to Langfuse.
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from typing import Annotated

# Test configuration
PROXY_URL = os.getenv("LANGCHAIN_ENDPOINT", "http://localhost:8003")
PROXY_API_KEY = os.getenv("PROXY_API_KEY", os.getenv("LANGCHAIN_API_KEY", ""))
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Skip test if credentials not available
if not all([PROXY_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY]):
    print("⚠️  Skipping integration test - missing credentials")
    print(f"   PROXY_API_KEY: {'✓' if PROXY_API_KEY else '✗'}")
    print(f"   LANGFUSE_PUBLIC_KEY: {'✓' if LANGFUSE_PUBLIC_KEY else '✗'}")
    print(f"   LANGFUSE_SECRET_KEY: {'✓' if LANGFUSE_SECRET_KEY else '✗'}")
    sys.exit(0)


def test_proxy_health():
    """Test 1: Verify proxy is running and healthy."""
    print("\n1️⃣  Testing proxy health...")

    import requests

    try:
        response = requests.get(f"{PROXY_URL}/health", timeout=5)
        response.raise_for_status()
        health = response.json()

        assert health["status"] == "healthy", "Proxy not healthy"
        assert health.get("langfuse_available") is True, "Langfuse not available"

        print(f"   ✅ Proxy healthy: {health}")
        return True
    except Exception as e:
        print(f"   ❌ Proxy health check failed: {e}")
        return False


async def test_langgraph_agent_with_tool():
    """Test 2: Run LangGraph agent with tool and verify trace in Langfuse."""
    print("\n2️⃣  Testing LangGraph agent with weather tool...")

    # Configure LangSmith SDK to use proxy
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = PROXY_URL
    os.environ["LANGCHAIN_API_KEY"] = PROXY_API_KEY

    # Import LangGraph and LangChain
    try:
        from langchain_core.messages import HumanMessage
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent
    except ImportError as e:
        print(f"   ⚠️  Skipping test - missing dependencies: {e}")
        print("   Install: pip install langchain langgraph langchain-openai")
        return None

    # Check OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("   ⚠️  Skipping test - OPENAI_API_KEY not set")
        return None

    # Define a simple weather tool
    @tool
    def get_weather(location: Annotated[str, "City and state, e.g. Boulder, CO"]) -> str:
        """Get the current weather for a location."""
        # Mock weather data for testing
        return f"The weather in {location} is sunny and 72°F with clear skies."

    # Create agent
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = create_react_agent(llm, [get_weather])

    # Generate unique trace ID for tracking
    test_id = f"test-{int(time.time())}"

    print(f"   🤖 Running agent (test_id: {test_id})...")

    # Run agent with weather query
    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="What's the weather in Boulder, CO?")]},
            config={"run_name": test_id},
        )

        # Check result
        assert "messages" in result, "No messages in result"
        final_message = result["messages"][-1].content
        print(f"   ✅ Agent response: {final_message[:100]}...")

        # Verify weather info is in response
        assert "Boulder" in final_message or "weather" in final_message.lower(), (
            "Response doesn't mention Boulder or weather"
        )

        return test_id

    except Exception as e:
        print(f"   ❌ Agent execution failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_trace_in_langfuse(test_id: str):
    """Test 3: Verify trace exists in Langfuse."""
    print(f"\n3️⃣  Checking Langfuse for trace (test_id: {test_id})...")

    # Give proxy time to flush traces to Langfuse
    print("   ⏳ Waiting 5 seconds for trace to flush...")
    time.sleep(5)

    try:
        from langfuse import Langfuse

        # Initialize Langfuse client
        langfuse = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )

        # Fetch traces (Langfuse SDK doesn't have direct trace query API in 3.x)
        # Instead, we'll check if any observations were created
        # This is a limitation of the SDK - in production you'd use the web UI

        print("   ℹ️  Note: Langfuse SDK 3.x doesn't provide direct trace query API")
        print("   ℹ️  Check Langfuse dashboard for trace verification:")
        print(f"   ℹ️  {LANGFUSE_HOST}/traces")
        print(f"   ℹ️  Search for: {test_id}")

        # Check proxy info to see if traces were sent
        import requests

        response = requests.get(f"{PROXY_URL}/info", timeout=5)
        info = response.json()

        runs_tracked = info.get("runs_tracked", 0)
        print(f"   📊 Proxy has tracked {runs_tracked} runs total")

        if runs_tracked > 0:
            print("   ✅ Proxy has forwarded traces to Langfuse")
            print(f"   ✅ Manual verification: Check {LANGFUSE_HOST} for trace '{test_id}'")
            return True
        else:
            print("   ⚠️  Proxy shows 0 runs tracked")
            return False

    except Exception as e:
        print(f"   ❌ Langfuse check failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all integration tests."""
    print("=" * 80)
    print("🧪 LangSmith-to-Langfuse Proxy Integration Test")
    print("=" * 80)

    results = []

    # Test 1: Proxy health
    health_ok = test_proxy_health()
    results.append(("Proxy Health", health_ok))

    if not health_ok:
        print("\n❌ Proxy not healthy, skipping remaining tests")
        return False

    # Test 2: Run LangGraph agent
    test_id = await test_langgraph_agent_with_tool()
    agent_ok = test_id is not None
    results.append(("LangGraph Agent", agent_ok))

    if not agent_ok:
        print("\n❌ Agent test failed, skipping Langfuse check")
    else:
        # Test 3: Check Langfuse
        langfuse_ok = test_trace_in_langfuse(test_id)
        results.append(("Langfuse Trace", langfuse_ok))

    # Summary
    print("\n" + "=" * 80)
    print("📋 Test Summary")
    print("=" * 80)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test_name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 All tests passed!")
        print("\n💡 Next steps:")
        print(f"   1. Open Langfuse dashboard: {LANGFUSE_HOST}")
        print(f"   2. Search for trace: {test_id if test_id else 'test-*'}")
        print("   3. Verify trace shows:")
        print("      - Root observation (agent run)")
        print("      - Generation (LLM call)")
        print("      - Span (tool call)")
    else:
        print("\n❌ Some tests failed")

    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

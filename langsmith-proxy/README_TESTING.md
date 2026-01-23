# Integration Testing

## Quick Test

Test that the proxy successfully forwards LangGraph traces to Langfuse:

```bash
# Install test dependencies
pip install -r test-requirements.txt

# Run integration test
python test_integration.py
```

## What the Test Does

1. **Proxy Health Check**: Verifies proxy is running and connected to Langfuse
2. **LangGraph Agent**: Runs a simple agent that:
   - Asks "What's the weather in Boulder, CO?"
   - Uses a `get_weather` tool (tests tool tracing)
   - Generates LLM calls (tests generation tracing)
   - Creates a trace hierarchy
3. **Langfuse Verification**: Checks that proxy forwarded traces

## Expected Output

```
🧪 LangSmith-to-Langfuse Proxy Integration Test
================================================================================

1️⃣  Testing proxy health...
   ✅ Proxy healthy: {'status': 'healthy', 'langfuse_available': True}

2️⃣  Testing LangGraph agent with weather tool...
   🤖 Running agent (test_id: test-1234567890)...
   ✅ Agent response: The weather in Boulder, CO is sunny and 72°F with clear skies.

3️⃣  Checking Langfuse for trace (test_id: test-1234567890)...
   ⏳ Waiting 5 seconds for trace to flush...
   📊 Proxy has tracked 3 runs total
   ✅ Proxy has forwarded traces to Langfuse
   ✅ Manual verification: Check https://cloud.langfuse.com for trace 'test-1234567890'

================================================================================
📋 Test Summary
================================================================================
  ✅ PASS  Proxy Health
  ✅ PASS  LangGraph Agent
  ✅ PASS  Langfuse Trace

🎉 All tests passed!

💡 Next steps:
   1. Open Langfuse dashboard: https://cloud.langfuse.com
   2. Search for trace: test-1234567890
   3. Verify trace shows:
      - Root observation (agent run)
      - Generation (LLM call)
      - Span (tool call)
```

## Requirements

- Proxy running on port 8003
- Environment variables set:
  - `PROXY_API_KEY` or `LANGCHAIN_API_KEY`
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_SECRET_KEY`
  - `OPENAI_API_KEY` (for LLM)

## Docker Test

Run the test inside Docker:

```bash
docker compose run --rm langsmith-proxy python test_integration.py
```

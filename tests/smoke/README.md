# Behavior Test Suite

Automated tests covering all system behaviors. Tests real integrations (Slack, Vector DB, LLM, etc.) to replace manual testing.

---

## Quick Start

```bash
# Run all behavior tests
make test-behaviors

# Run specific behaviors
pytest tests/smoke/test_behaviors.py -v -s -k "slack"
pytest tests/smoke/test_behaviors.py -v -s -k "agent"
pytest tests/smoke/test_behaviors.py -v -s -k "vector"
pytest tests/smoke/test_behaviors.py -v -s -k "llm"

# Run with real Slack
E2E_USE_REAL_SLACK=true E2E_SLACK_CHANNEL=C123456 make test-behaviors
```

---

## What It Tests

### ✅ Agent System
- All agents discoverable with proper metadata
- Each agent can execute successfully
- Agent responses contain expected content

### ✅ Slack Integration (Real if configured)
- Auth and bot info retrieval
- List channels bot has access to
- Send and delete messages
- Thread creation and replies
- Reactions

### ✅ Vector Database (Qdrant)
- Create/delete collections
- Insert vectors and payloads
- Search with similarity
- Bulk operations (100+ vectors)

### ✅ LLM Provider
- Different models (gpt-4o-mini, gpt-4o)
- Streaming responses
- Function/tool calling

### ✅ RAG Pipeline
- Full retrieve → generate flow
- Context injection
- Response quality

### ✅ Caching (Redis)
- Set/get/delete operations
- TTL behavior

### ✅ Error Handling
- Invalid agent requests (404)
- LLM failures (graceful degradation)

### ✅ Performance
- Response time benchmarks
- Simple query < 30s

---

## Configuration

### Required

```bash
# LLM Provider
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Vector Database
VECTOR_HOST=localhost
VECTOR_PORT=6333
```

### Optional

```bash
# Slack (for real Slack tests)
SLACK_BOT_TOKEN=xoxb-...
E2E_SLACK_CHANNEL=C123456       # Test channel ID
E2E_USE_REAL_SLACK=true         # Enable real Slack tests

# Agent Service
AGENT_SERVICE_URL=http://localhost:8001

# Redis Cache
CACHE_REDIS_URL=redis://localhost:6379

# Web Search
TAVILY_API_KEY=tvly-...
```

---

## Test Modes

### Mock Mode (Default)
Mocks external APIs (Slack) to avoid rate limits.

```bash
pytest tests/smoke/test_behaviors.py -v -s
```

### Real Slack Mode
Tests actual Slack API integration.

**Setup:**
1. Create test channel (e.g., `#bot-testing`)
2. Invite bot to channel
3. Get channel ID (right-click → View channel details)
4. Set environment:

```bash
export E2E_USE_REAL_SLACK=true
export E2E_SLACK_CHANNEL=C123456789
```

**Run:**
```bash
make test-behaviors
```

**Note:** Tests clean up after themselves (delete test messages).

---

## CI Integration

```yaml
name: Behavior Tests

on:
  pull_request:
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  behavior-tests:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

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
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run behavior tests
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          VECTOR_HOST: localhost
          CACHE_REDIS_URL: redis://localhost:6379
        run: make test-behaviors
```

---

## Troubleshooting

### Slack Tests Skipped

**Problem:** `SLACK_BOT_TOKEN not configured`

**Solution:**
```bash
export SLACK_BOT_TOKEN=xoxb-...
export E2E_SLACK_CHANNEL=C123456
```

---

### Vector DB Tests Skipped

**Problem:** `VECTOR_HOST not configured`

**Solution:**
```bash
# Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# Set environment
export VECTOR_HOST=localhost
```

---

### Agent Service Tests Skipped

**Problem:** `Agent service not running`

**Solution:**
```bash
# Start agent service
cd agent-service
python app.py &

# Set URL
export AGENT_SERVICE_URL=http://localhost:8001
```

---

## Usage Patterns

### Before Releases
```bash
make test-behaviors
```

### Weekly Validation
```bash
# With real Slack for thorough testing
E2E_USE_REAL_SLACK=true E2E_SLACK_CHANNEL=C123456 make test-behaviors
```

### CI/CD
```bash
# Automated daily runs
make test-behaviors
```

### Debug Specific Behaviors
```bash
# Only test Slack functionality
pytest tests/smoke/test_behaviors.py::test_slack_auth_and_bot_info -v -s

# Only test agents
pytest tests/smoke/test_behaviors.py -v -s -k "agent"

# Only test vector DB
pytest tests/smoke/test_behaviors.py -v -s -k "vector"
```

---

## Adding New Tests

Add to `test_behaviors.py`:

```python
@pytest.mark.behavior
@pytest.mark.asyncio
async def test_new_behavior():
    """Test new system behavior."""
    # Your test here
    pass
```

---

## Summary

**Never manually test again!**

Run `make test-behaviors` to validate:
- ✅ All agents work
- ✅ Slack integration works
- ✅ Vector DB works
- ✅ LLM works
- ✅ RAG pipeline works
- ✅ Caching works
- ✅ Error handling works
- ✅ Performance is acceptable

**Runtime:** 15-30 minutes
**Coverage:** All major system behaviors
**Slack:** Can test real Slack API if configured

# Smoke & Comprehensive Test Suite

Automated test packs to replace manual testing. Run these before releases or after major changes.

---

## Quick Start

```bash
# Quick smoke tests (~2-5 minutes)
make test-smoke

# End-to-end workflows (~5-10 minutes)
make test-e2e

# Comprehensive behavior tests (~15-30 minutes)
make test-comprehensive

# Run everything
make test-all-smoke
```

---

## Test Suites

### 1. Smoke Tests (`test_smoke_suite.py`)
**Purpose:** Quick validation that critical systems work
**Runtime:** 2-5 minutes
**When:** After code changes, before commits

**What it tests:**
- ✅ Slack connection and authentication
- ✅ Vector database (Qdrant) connection and search
- ✅ LLM provider (OpenAI/Anthropic) works
- ✅ Agent service health and agent discovery
- ✅ Agent invocation (simple test)
- ✅ Bot message handling
- ✅ RAG retrieval
- ✅ Web search (if configured)

**Usage:**
```bash
# Run smoke tests
make test-smoke

# Run specific smoke test
pytest tests/smoke/test_smoke_suite.py::test_slack_connection -v -s

# Run without Slack tests
pytest tests/smoke/test_smoke_suite.py -v -s -k "not slack"
```

---

### 2. End-to-End Tests (`test_end_to_end.py`)
**Purpose:** Test complete user workflows
**Runtime:** 5-10 minutes
**When:** Before releases, after major features

**What it tests:**
- ✅ Simple Q&A flow (user question → bot response)
- ✅ Agent invocation workflow
- ✅ RAG query workflow (retrieve docs → answer)
- ✅ Thread conversation with context
- ✅ File attachment processing
- ✅ Web search queries

**Usage:**
```bash
# Run E2E tests (mocked Slack)
make test-e2e

# Run E2E with REAL Slack (recommended for thorough testing)
E2E_USE_REAL_SLACK=true E2E_SLACK_CHANNEL=C123456 make test-e2e

# Run specific E2E test
pytest tests/smoke/test_end_to_end.py::test_e2e_simple_question_answer -v -s
```

---

### 3. Comprehensive Behavior Tests (`test_comprehensive_behaviors.py`)
**Purpose:** Thorough validation of ALL system behaviors
**Runtime:** 15-30 minutes
**When:** Before major releases, weekly validation

**What it tests:**
- ✅ **All Agents:** Discovery, metadata, execution for each agent
- ✅ **Slack (Real if configured):**
  - Auth and bot info
  - List channels
  - Send/delete messages
  - Thread creation
  - Reactions
- ✅ **Vector DB:**
  - Create/delete collections
  - Insert/search vectors
  - Bulk operations
- ✅ **LLM Provider:**
  - Different models (gpt-4o-mini, gpt-4o)
  - Streaming responses
  - Function/tool calling
- ✅ **RAG Pipeline:** Full retrieve → generate flow
- ✅ **Caching:** Redis operations
- ✅ **Error Handling:** Invalid requests, LLM failures
- ✅ **Performance:** Response time benchmarks

**Usage:**
```bash
# Run comprehensive tests
make test-comprehensive

# Run specific behavior tests
pytest tests/smoke/test_comprehensive_behaviors.py -v -s -k "slack"
pytest tests/smoke/test_comprehensive_behaviors.py -v -s -k "vector"
pytest tests/smoke/test_comprehensive_behaviors.py -v -s -k "llm"

# Run with real Slack
E2E_USE_REAL_SLACK=true E2E_SLACK_CHANNEL=C123456 make test-comprehensive
```

---

## Configuration

### Required Environment Variables

```bash
# LLM Provider (REQUIRED)
LLM_API_KEY=sk-...              # OpenAI or Anthropic API key
LLM_MODEL=gpt-4o-mini           # Model to use

# Vector Database (REQUIRED for RAG tests)
VECTOR_HOST=localhost
VECTOR_PORT=6333
```

### Optional Environment Variables

```bash
# Slack (for real Slack tests)
SLACK_BOT_TOKEN=xoxb-...
E2E_SLACK_CHANNEL=C123456       # Test channel ID
E2E_USE_REAL_SLACK=true         # Enable real Slack tests

# Web Search (optional)
TAVILY_API_KEY=tvly-...

# Agent Service
AGENT_SERVICE_URL=http://localhost:8001

# Redis Cache
CACHE_REDIS_URL=redis://localhost:6379
```

---

## Test Modes

### Mock Mode (Default)
Mocks external APIs (Slack) to avoid rate limits and costs.

```bash
pytest tests/smoke/ -v -s
```

### Real Slack Mode
Uses real Slack API for thorough integration testing.

**Setup:**
1. Create a dedicated test channel (e.g., `#bot-testing`)
2. Invite your bot to the channel
3. Get the channel ID (right-click channel → View channel details)
4. Set environment variables:

```bash
export E2E_USE_REAL_SLACK=true
export E2E_SLACK_CHANNEL=C123456789
```

**Run tests:**
```bash
make test-comprehensive
```

**Benefits:**
- Tests real Slack API behavior
- Validates auth, permissions, rate limits
- Catches API changes
- Tests actual message formatting

**Note:** Tests will clean up after themselves (delete test messages).

---

## CI Integration

Add to `.github/workflows/smoke-tests.yml`:

```yaml
name: Smoke Tests

on:
  pull_request:
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  smoke-tests:
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

      - name: Run smoke tests
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          VECTOR_HOST: localhost
          VECTOR_PORT: 6333
          CACHE_REDIS_URL: redis://localhost:6379
        run: make test-smoke

      - name: Run E2E tests
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          VECTOR_HOST: localhost
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
        run: make test-e2e
```

---

## Troubleshooting

### Slack Tests Failing

**Problem:** `channel_not_found` error

**Solution:** Update `E2E_SLACK_CHANNEL` to a real channel ID where bot is a member.

---

### Vector DB Tests Skipped

**Problem:** `VECTOR_HOST not configured`

**Solution:**
```bash
# Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# Set environment
export VECTOR_HOST=localhost
export VECTOR_PORT=6333
```

---

### LLM Tests Failing

**Problem:** `LLM_API_KEY not configured` or rate limits

**Solution:**
```bash
# Set API key
export LLM_API_KEY=sk-...

# Use cheaper model for tests
export LLM_MODEL=gpt-4o-mini

# Wait if rate limited
sleep 60
```

---

### Agent Service Tests Skipped

**Problem:** `Agent service not running`

**Solution:**
```bash
# Start agent service
cd agent-service
python app.py &

# Or use Docker
docker compose up agent-service -d

# Set URL
export AGENT_SERVICE_URL=http://localhost:8001
```

---

## Development Workflow

### Before Committing
```bash
make test-smoke
```

### Before Creating PR
```bash
make test-e2e
```

### Before Release
```bash
make test-comprehensive
```

### Weekly Validation
```bash
# Schedule via cron or CI
make test-all-smoke
```

---

## Adding New Tests

### Add to Smoke Suite
For quick validation of new critical features:

```python
# tests/smoke/test_smoke_suite.py

@pytest.mark.asyncio
@pytest.mark.smoke
async def test_new_feature(smoke_env):
    """Smoke: Verify new feature works."""
    # Your test here
    pass
```

### Add to E2E Suite
For new user workflows:

```python
# tests/smoke/test_end_to_end.py

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_new_workflow(e2e_env):
    """E2E: User does X → System does Y."""
    # Your test here
    pass
```

### Add to Comprehensive Suite
For thorough validation:

```python
# tests/smoke/test_comprehensive_behaviors.py

@pytest.mark.comprehensive
@pytest.mark.asyncio
async def test_new_behavior():
    """Test all aspects of new behavior."""
    # Your test here
    pass
```

---

## Tips

1. **Run smoke tests often** - They're fast and catch issues early
2. **Run E2E before releases** - Validates complete workflows
3. **Run comprehensive weekly** - Thorough validation
4. **Use real Slack occasionally** - Catches API changes
5. **Monitor test runtime** - Keep smoke tests <5 min
6. **Clean up test data** - Tests should not leave artifacts
7. **Use unique IDs** - Avoid conflicts with concurrent tests

---

## Summary

**Replace manual testing with:**
- `make test-smoke` - Quick validation (2-5 min)
- `make test-e2e` - Workflow validation (5-10 min)
- `make test-comprehensive` - Full validation (15-30 min)

**Never manually test again!** 🎉

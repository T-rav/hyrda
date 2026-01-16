# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL: Testing is Mandatory

**ALWAYS write unit tests for code changes before committing.** Every new function, class, or feature modification MUST include comprehensive tests.

**Testing Requirements:**
- ✅ **New features**: Write tests BEFORE committing
- ✅ **Bug fixes**: Add regression tests that reproduce the bug
- ✅ **Refactoring**: Ensure existing tests pass, add tests for new paths
- ✅ **API changes**: Test all endpoints and error cases
- ❌ **Never commit untested code** - tests are non-negotiable

## 🚨 CRITICAL: Never Skip Commit Hooks

**NEVER** use `git commit --no-verify` or `--no-hooks` flags. Always fix code issues first.

### Commit Process
1. Fix all linting, formatting, and security issues identified by pre-commit hooks
2. Ensure all tests pass (`make test`)
3. Only commit once code passes all quality checks
4. Pre-commit hooks maintain code quality and security - never bypass them

**Code quality is non-negotiable.** Broken code should never be committed.

## 🔒 Security Standards

InsightMesh follows the 8th Light Host Hardening Policy for all infrastructure.

**Security Commands:**
```bash
make security         # Run Bandit code security scanner (50+ checks)
make security-docker  # Scan Docker images with Trivy for CVEs and secrets
make security-full    # Run both Bandit + Trivy
make lint             # Includes security checks (Ruff + Pyright + Bandit)
make quality          # Full pipeline including security scans
```

**Key Requirements:**
- ✅ **Secrets Management:** Never commit secrets (`.env` in `.gitignore`)
- ✅ **Container Security:** All containers run as non-root user (UID 1000)
- ✅ **Code Scanning:** 50+ Bandit security checks (SQL injection, crypto, deserialization)
- ✅ **Docker Scanning:** Trivy scans for CVEs and secrets in images
- ✅ **CI Integration:** Security scans run automatically on every push

**Before Committing:**
1. Run `make lint` to catch security issues automatically
2. Verify Bandit security scan passes (included in pre-commit hooks)
3. For Docker changes, run `make security-docker` to scan images

## Development Commands

### Setup and Installation
```bash
make install      # Install Python dependencies
make setup-dev    # Install dev tools + pre-commit hooks (run once)
```

### Running the Application
```bash
make run          # Run the Slack bot (requires .env file)
docker compose up -d  # Run full stack (bot + services)
```

### Testing and Code Quality
```bash
make test         # Run test suite with pytest (565 tests)
make lint         # Auto-fix linting, formatting, and import issues
make lint-check   # Check code quality without fixing (used by pre-commit)
make quality      # Run complete pipeline: linting + type checking + tests
make ci           # Run complete CI pipeline locally (quality + tests + security + build)
```

### Docker
```bash
make docker-build              # Build Docker images
make docker-run                # Run Docker container with .env
docker logs -f insightmesh-bot # View bot logs
```

### Utilities
```bash
make clean        # Remove caches and build artifacts
```

## Quality Tooling

### Unified Linting System
Pre-commit hooks and CI use **identical Makefile commands** to prevent environment mismatches:
- **Ruff**: Fast linting, formatting, and import sorting
- **Pyright**: Type checking (strict mode)
- **Bandit**: Security vulnerability scanning (50+ checks)

**Benefits**: Same tools, versions, and config across local dev, pre-commit, and CI. No more "works locally but fails in CI"!

### Quick Reference

| Situation | Command | Purpose |
|-----------|---------|---------|
| **Before any changes** | `make test` | Establish baseline |
| **After editing `.py` file** | `make lint` | Auto-fix formatting/imports |
| **After significant changes** | `make lint-check` | Verify code quality |
| **Before committing** | `make quality` | Complete pipeline |
| **If pre-commit fails** | `make lint` → fix → commit | Fix quality issues |

## Environment Configuration

The application requires a `.env` file in the project root. Copy `.env.example` as a starting point.

### Basic Configuration
```bash
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# LLM Provider (choose one)
LLM_PROVIDER=openai  # openai, anthropic, ollama
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4o-mini

# Cache
CACHE_REDIS_URL=redis://localhost:6379
```

### RAG Configuration (Optional)
```bash
# Vector Database
VECTOR_ENABLED=true
VECTOR_PROVIDER=qdrant
VECTOR_HOST=localhost
VECTOR_PORT=6333

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

### Web Search Configuration
```bash
TAVILY_API_KEY=your-tavily-api-key  # Web search via Tavily
PERPLEXITY_API_KEY=your-perplexity-api-key  # Optional: Deep research
```

## Architecture Overview

Production-ready Python Slack bot with:
- **Microservices**: Bot, agent-service, control-plane, tasks
- **RAG capabilities**: Vector search with Qdrant
- **Agent system**: Specialized AI agents via HTTP API
- **Multi-LLM support**: OpenAI, Anthropic, or Ollama

### Core Structure
- **bot/app.py**: Main application entry point
- **bot/config/**: Pydantic settings with environment-based configuration
- **bot/handlers/**: Event and message handling, agent processes
- **bot/services/**: Core services (RAG, LLM providers, vector storage)
- **bot/utils/**: Error handling and logging utilities
- **ingest/**: Google Drive document ingestion with OAuth2

### Message Flow
1. Slack events → `bot/handlers/event_handlers.py`
2. Message processing → `bot/handlers/message_handlers.py`
3. LLM API calls → `bot/services/llm_service.py`
4. Response formatting → `bot/services/formatting.py`
5. Slack response → `bot/services/slack_service.py`

### Document Ingestion (Google Drive)
Access the tasks dashboard at http://localhost:5001

**Workflow**: Update .env → Authenticate → Create Scheduled Task

1. Update `.env` with OAuth credentials (from Google Cloud Console)
2. Authenticate: `open http://localhost:5001/api/gdrive/auth`
3. Create scheduled task via web UI (job type: "Google Drive Ingestion")

**Supported Formats**: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Google Workspace files

## Testing Framework & Quality Standards

**🎯 MANDATORY: All code changes MUST include comprehensive tests and pass 100% of the test suite.**

The project maintains a **565/565 test success rate (100%)** - this standard must be preserved.

### Test Commands
```bash
make test                    # Full test suite (565 tests)
make test-coverage          # Tests with coverage report (requires >70%, currently ~72%)
make test-file FILE=test_name.py  # Run specific test file
```

### Test Coverage Requirements
- **Minimum Coverage**: 70% (enforced by CI)
- **Current Coverage**: ~72%
- **All new functions/classes MUST have tests**
- **Critical paths require 100% coverage**

### Code Quality Standards

#### Type Annotations (Required)
```python
# ✅ REQUIRED: All functions must have type hints
async def process_message(
    text: str,
    user_id: str,
    service: SlackService
) -> bool:
    """Process a message with proper typing."""
    return True

# ❌ FORBIDDEN: Untyped functions
def process_message(text, user_id, service):
    return True
```

### Development Workflow (MANDATORY)

#### For Every Code Change:

1. **Write Tests First** (TDD approach preferred)
2. **Run Quality Checks**: `make quality` before every commit
3. **Commit with Verified Quality**: Only commit when all checks pass

#### For Bug Fixes:

1. **Write Reproduction Test** (should fail initially)
2. **Fix the Bug** (test should now pass)
3. **Add Edge Case Tests** (prevent regression)

### Integration with CI/CD

**GitHub Actions Pipeline:**
- **Triggered on**: Every push and PR
- **Runs**: `make ci` (quality + tests + security + build)
- **Blocks merge**: If any test fails, coverage < 70%, or security issues found

**Pre-commit Hooks:**
- Ruff (linting, formatting, import sorting)
- Pyright (type checking with strict mode)
- Bandit (security vulnerability scanning)
- File cleanup (trailing whitespace, line endings, merge conflicts)
- Syntax validation (Python AST, YAML, TOML, JSON)

## Production Deployment

### Docker Deployment (Recommended)

```bash
docker compose -f docker-compose.prod.yml up -d
```

**Features:**
- Health checks on port 8080 (`/health`, `/ready`, `/metrics`)
- Automatic restart on failure
- Log rotation and persistent storage
- Resource limits (512M memory, 0.5 CPU)
- Container isolation and security
- Non-root user (UID 1000)

### Environment Variables (Production)

Required:
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
LLM_API_URL=https://your-api.com
LLM_API_KEY=your-api-key
```

Optional:
```bash
ENVIRONMENT=production  # Enables JSON logging
LOG_LEVEL=INFO         # DEBUG, INFO, WARNING, ERROR
HEALTH_PORT=8080       # Health check server port
```

---

## 📚 Appendix

### A. File Attachment Handling - Slack API Limitation

The bot can process file attachments (PDF, Word, Excel, PowerPoint, text files) in threads.

**✅ What Works:**
- Upload file with bot present → Bot downloads and caches content
- Continue discussion in same thread → Bot remembers file content

**❌ Slack API Limitation:**
The bot **cannot access files uploaded before it joined a channel**, even though it can see message history. This is a Slack security feature - file URLs are permission-gated at upload time.

**Workarounds:**
1. Re-upload the document after adding the bot
2. Add bot BEFORE sharing sensitive documents
3. Use RAG knowledge base - Pre-ingest documents via tasks service

### B. RAG & LLM Integration

**Supported LLM Providers:**
- **OpenAI**: GPT-4, GPT-3.5
- **Anthropic**: Claude 3 (Haiku, Sonnet, Opus)
- **Ollama**: Local models (Llama 2, Code Llama)

**RAG Pipeline:**
1. **Ingestion**: Documents chunked and embedded into Qdrant
2. **Query Processing**: User questions embedded for similarity search
3. **Retrieval**: Most relevant chunks retrieved
4. **Augmentation**: Retrieved context added to LLM prompt
5. **Web Search** (if needed): LLM triggers Tavily search for current info
6. **Generation**: LLM generates response with enhanced context

**Web Search Integration:**
- **Tavily Search**: Fast web search results
- **Perplexity Deep Research**: Long-form research with citations
- **Function Calling**: LLM automatically decides when to search
- **Langfuse Tracing**: All tool calls traced for observability

### C. Relationship Verification System

Advanced system for company profile agent to prevent false positives when identifying past client relationships.

**How It Works:**
- **Internal Search Tool**: Deep search with entity boosting (20% boost for company name in content, 30% in title)
- **Langfuse Prompt Versioning**: Prompt v10 trusts internal search results
- **Index Filtering**: -50% penalty for index/overview files

**Integration Tests:**
`evals/relationship_detection/test_relationship_verification_integration.py`

**Update Prompt:**
```bash
PYTHONPATH=bot venv/bin/python scripts/fix_final_report_prompt.py
```
Then promote in Langfuse UI.

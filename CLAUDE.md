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

**Progressive Validation (Fastest to Slowest):**
```bash
make lint         # Auto-fix linting, formatting, and import issues (~2s)
make test-fast    # Quick validation - unit tests only (~20s)
make test-service SERVICE=bot  # Test specific service (varies by service)
make quality      # Complete pipeline: linting + type checking + tests (~2-3min)
make ci           # Full CI pipeline locally (quality + tests + security + build)
```

**Smart Testing Strategy:**
```bash
# After small changes - quick feedback
make lint && make test-fast

# Before committing - full validation
make quality

# Before pushing - CI simulation
make ci
```

### Docker
```bash
make docker-build              # Build Docker images
make docker-run                # Run Docker container with .env
docker logs -f insightmesh-bot # View bot logs
```

### Document Ingestion - Scheduled Google Drive Tasks
```bash
# PRODUCTION INGESTION METHOD
# Document ingestion is now handled via scheduled tasks in the tasks service
# Access the tasks dashboard at http://localhost:5001 (or your server URL)

# WORKFLOW: Update .env → Authenticate → Create Scheduled Task

# 1. Update .env with OAuth credentials (from Google Cloud Console):
# GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
# GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
# SERVER_BASE_URL=http://localhost:5001  # Must match Google Cloud Console redirect URI
# OAUTH_ENCRYPTION_KEY=your-fernet-key  # For credential storage

# Also ensure these are configured:
# - Vector database (Qdrant): VECTOR_HOST, VECTOR_PORT
# - Embedding service: EMBEDDING_PROVIDER, EMBEDDING_API_KEY
# - OpenAI API key (for audio/video transcription): OPENAI_API_KEY

# 2. Authenticate Google Drive (saves OAuth credential to database):
open http://localhost:5001/api/gdrive/auth
# - Grant Google Drive permissions in OAuth popup
# - Success page appears and auto-closes after 3 seconds
# - Credential saved encrypted in database with ID (e.g., "prod_gdrive")

# 3. Create Google Drive Ingestion Scheduled Task:
open http://localhost:5001
# In the tasks dashboard web UI:
#    - Job Type: "Google Drive Ingestion"
#    - Credential ID: "prod_gdrive" (the ID from step 2)
#    - Folder ID: "0AMXFYdnvxhbpUk9PVA" (production documents folder)
#    - Set schedule (e.g., daily at 3 AM)
#    - Optional: Add custom metadata for all documents

# Supported Formats:
# - Documents: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Google Workspace files
# - Audio: MP3, WAV, M4A, AAC, OGG, FLAC, WebM (transcribed via OpenAI Whisper)
# - Video: MP4, MOV, AVI, MKV, WebM (audio extracted and transcribed via OpenAI Whisper)
# Includes comprehensive metadata: file paths, permissions, owners, sharing settings
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
- **Microservices**: Bot, agent-service, control-plane, tasks, rag-service
- **RAG capabilities**: Vector search with Qdrant
- **Agent system**: Specialized AI agents via HTTP API
- **Multi-LLM support**: OpenAI, Anthropic, or Ollama
- **Web UI**: LibreChat for direct knowledge base access

### Service Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Slack Bot     │────▶│  Control Plane   │◀────│  Agent Service  │
│    (bot/)       │     │ (control_plane/) │     │(agent-service/) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  RAG Service    │────▶│   MySQL/Redis    │◀────│  Tasks Service  │
│ (rag-service/)  │     │   (Data/Cache)   │     │    (tasks/)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│     Qdrant      │     │    LibreChat     │
│ (Vector Store)  │     │   (Web UI/3443)  │
└─────────────────┘     └──────────────────┘
```

### Service Ports & Endpoints

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **Bot** | 8080 | `http://localhost:8080` | Slack event handling |
| **Control Plane** | 6001 | `https://localhost:6001` | Agent registry, management UI |
| **Agent Service** | 8000 | `https://localhost:8000` | LangGraph HTTP API |
| **Tasks** | 5001 | `http://localhost:5001` | Task scheduler, Google Drive auth |
| **RAG Service** | 8002 | `http://localhost:8002` | Vector search API |
| **LibreChat** | 3443 | `https://localhost:3443` | Web UI (HTTPS) |
| **LibreChat HTTP** | 3080 | `http://localhost:3080` | Web UI (HTTP→HTTPS redirect) |
| **Qdrant** | 6333 | `http://localhost:6333` | Vector database |
| **MySQL** | 3306 | `localhost:3306` | Relational database |
| **Redis** | 6379 | `localhost:6379` | Cache |

### LibreChat Web UI

LibreChat provides a ChatGPT-like interface for direct RAG interaction:

**Start LibreChat:**
```bash
docker compose -f docker-compose.librechat.yml up -d
```

**Access:**
- HTTPS: `https://localhost:3443` (recommended)
- HTTP: `http://localhost:3080` (redirects to HTTPS)

**Architecture:**
- `librechat` container: Node.js application (internal port 3080)
- `librechat-nginx` container: Nginx reverse proxy with SSL
- `librechat-mongodb` container: User data storage

**SSL Certificates (Local Development):**
```bash
# Generate trusted local certificates
brew install mkcert
mkcert -install
mkcert localhost 127.0.0.1 ::1
cp localhost+2.pem .ssl/librechat-cert.pem
cp localhost+2-key.pem .ssl/librechat-key.pem

# Restart to apply
docker compose -f docker-compose.librechat.yml restart librechat-nginx
```

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

The project maintains a **100% test success rate** across all microservices - this standard must be preserved.

### Test Commands

**Progressive Validation Approach:**
```bash
# 1. Syntax check - Fast feedback (2s)
make lint

# 2. Unit tests only - Quick validation (20s)
make test-fast

# 3. Service-specific - Test what you changed
make test-service SERVICE=bot        # Bot service only
make test-service SERVICE=tasks      # Tasks service only
cd bot && pytest tests/test_specific_feature.py -v  # Single file

# 4. Full test suite - Before commit (2-3min)
make test

# 5. With coverage report - Validate coverage targets
make test-coverage          # Requires >70% coverage

# 6. Full CI pipeline - Before push (5-10min)
make ci
```

**Test Markers for Selective Testing:**
```bash
# Run only unit tests (fast, excludes integration/slow/smoke tests)
pytest -m "not integration and not slow and not smoke"

# Run only integration tests (when needed)
pytest -m integration

# Run only smoke tests (quick health checks)
pytest -m smoke

# Run tests matching a pattern
pytest -k "test_auth"

# Run specific test file with verbose output
pytest tests/test_feature.py -v
```

**Test Markers Reference:**
- `@pytest.mark.unit` - Unit tests (default, always run)
- `@pytest.mark.integration` - Integration tests requiring external services
- `@pytest.mark.smoke` - Quick health checks (require running services)
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.system_flow` - End-to-end system tests

### Test Coverage Requirements
- **Minimum Coverage**: 70% (enforced by CI)
- **All new functions/classes MUST have tests**
- **Critical paths require 100% coverage**
- **Coverage should increase or stay constant, never decrease**

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
2. **Run Quality Checks**: Use progressive validation based on change scope
3. **Commit with Verified Quality**: Only commit when all checks pass

#### For Bug Fixes:

1. **Write Reproduction Test** (should fail initially)
2. **Fix the Bug** (test should now pass)
3. **Add Edge Case Tests** (prevent regression)

#### Agent Self-Validation Checklist

After completing a code change, validate your work progressively:

**Level 1: Syntax Validation (2s)**
- [ ] `make lint` passes without errors
- [ ] No type checking errors from Pyright
- [ ] No security issues from Bandit

**Level 2: Unit Testing (20s)**
- [ ] `make test-fast` passes (unit tests only)
- [ ] All modified services have passing tests
- [ ] Coverage maintains >70% threshold

**Level 3: Service-Specific Testing (varies)**
- [ ] For bot changes: `cd bot && pytest tests/test_<feature>.py -v`
- [ ] For agent-service: `cd agent-service && pytest tests/test_<feature>.py -v`
- [ ] For tasks changes: `cd tasks && pytest -m "not integration" tests/test_<feature>.py`
- [ ] Only run integration tests if modifying subprocess, ffmpeg, or file operations

**Level 4: Full Validation (2-3min)**
- [ ] `make quality` passes completely
- [ ] All pre-commit hooks pass
- [ ] No test regressions

**Level 5: CI Simulation (5-10min)**
- [ ] `make ci` completes successfully
- [ ] Docker builds succeed
- [ ] Security scans pass (Bandit + Trivy)

**Git Commit Decision Matrix:**

| Change Type | Required Validation | Time |
|-------------|-------------------|------|
| Documentation, comments | `make lint` | 2s |
| Small refactor (renaming) | `make lint` + `make test-fast` | 22s |
| Single function change | `make lint` + `make test-service` | varies |
| New feature or bug fix | `make quality` | 2-3min |
| Critical changes (auth, security) | `make ci` | 5-10min |
| Before pushing to remote | `make ci` | 5-10min |

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
Then promote the new version to production in Langfuse UI.

## LangSmith to Langfuse Proxy

The project includes a LangSmith-compatible proxy that redirects LangGraph agent traces to Langfuse in production while preserving LangSmith for local development.

**Quick Start:**
```bash
# Production: Route traces to Langfuse
./scripts/toggle-langsmith-proxy.sh proxy

# Local Dev: Use LangSmith directly
./scripts/toggle-langsmith-proxy.sh direct

# Check current mode
./scripts/toggle-langsmith-proxy.sh status
```

**Documentation:** See [LANGSMITH_PROXY.md](LANGSMITH_PROXY.md) for complete details.

**Benefits:**
- 💰 No LangSmith cloud costs in production
- 📊 Unified observability in Langfuse
- 🛠️ LangSmith UI for local debugging
- 🔌 Zero code changes (environment variables only)

**Architecture:**
- LangGraph agents → LangSmith SDK → Proxy → Langfuse
- Proxy converts LangSmith trace format to Langfuse format
- Transparent to agents (they think they're talking to LangSmith)

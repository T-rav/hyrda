# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL: Never Skip Commit Hooks

**NEVER** use `git commit --no-verify` or `--no-hooks` flags. Always fix code issues first.

### 🔄 Unified Linting System
Pre-commit hooks and CI now use **identical scripts and tool versions** to prevent environment mismatches:
- **Same Script**: `./scripts/lint.sh` used by both local and CI  
- **Same Versions**: `requirements-dev.txt` pins exact tool versions
- **Same Config**: `pyproject.toml` shared across environments

This eliminates the "works locally but fails in CI" problem!

### Commit Process:
1. Fix all linting, formatting, and security issues identified by pre-commit hooks
2. Ensure all tests pass (`make test`)
3. Only commit once code passes all quality checks
4. Pre-commit hooks are there to maintain code quality and security

### If hooks fail:
- Fix the issues reported (imports, formatting, security, type hints)
- Run `make lint` to auto-fix what can be fixed automatically  
- Manually fix remaining issues
- Then commit normally

**Code quality is non-negotiable.** Broken code should never be committed.

## Development Commands

### Setup and Installation
```bash
make install      # Install Python dependencies
```

### Running the Application
```bash
make run          # Run the Slack bot (requires .env file)
```

### Testing
```bash
make test         # Run test suite with pytest
```

### Docker
```bash
make docker-build # Build Docker image
make docker-run   # Run Docker container with .env
```

### Document Ingestion - Google Drive Only
```bash
# THE ONLY SUPPORTED INGESTION METHOD
# Ingest documents from Google Drive with comprehensive metadata
cd ingest && python google_drive_ingester.py --folder-id "1ABC123DEF456GHI789"
cd ingest && python google_drive_ingester.py --folder-id "1ABC123DEF456GHI789" --metadata '{"department": "engineering", "project": "docs"}'

# First-time setup requires Google OAuth2 credentials
# See ingest/README.md for detailed setup instructions
# Includes file paths, permissions, and access control metadata
```


### Utilities
```bash
make clean        # Remove caches and build artifacts
```

## Environment Configuration

The application requires a `.env` file in the project root. Copy `.env.example` as a starting point:

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
VECTOR_PROVIDER=chroma  # chroma, pinecone
VECTOR_URL=http://localhost:8000

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

# Retrieval Settings
RAG_MAX_CHUNKS=5
RAG_SIMILARITY_THRESHOLD=0.7
```

### Quick Setup Examples

**OpenAI + ChromaDB (Local):**
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-key
VECTOR_PROVIDER=chroma
VECTOR_URL=./chroma_db
```

**Anthropic + Pinecone (Cloud):**
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=your-anthropic-key
VECTOR_PROVIDER=pinecone
VECTOR_API_KEY=your-pinecone-key
```

**Ollama (Local, No RAG):**
```bash
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama2
VECTOR_ENABLED=false
```

## Architecture Overview

This is a production-ready Python Slack bot with **RAG (Retrieval-Augmented Generation)** capabilities, direct LLM provider integration, and comprehensive testing.

### 🏗️ Core Architecture

#### New RAG-Enabled Design
- **Direct LLM Integration**: OpenAI, Anthropic, or Ollama (no proxy required)
- **Vector Database**: ChromaDB or Pinecone for knowledge storage
- **Embedding Service**: Configurable text vectorization
- **RAG Pipeline**: Retrieval-augmented response generation
- **Document Ingestion**: CLI tool for knowledge base management

#### Core Structure
- **bot/app.py**: Main application entry point with async Socket Mode handler
- **bot/config/**: Pydantic settings with environment-based configuration
- **bot/handlers/**: Event and message handling, including agent process management
- **bot/services/**: Core services including RAG, LLM providers, and vector storage
- **bot/utils/**: Error handling and logging utilities
- **ingest/**: Google Drive document ingestion system with OAuth2 authentication

### Key Components

#### Settings Management (config/settings.py)
Uses Pydantic with environment variable prefixes:
- `SlackSettings` (SLACK_*)
- `LLMSettings` (LLM_*)  
- `AgentSettings` (AGENT_*)

#### Message Flow
1. Slack events → `bot/handlers/event_handlers.py`
2. Message processing → `bot/handlers/message_handlers.py`
3. LLM API calls → `bot/services/llm_service.py`
4. Response formatting → `bot/services/formatting.py`
5. Slack response → `bot/services/slack_service.py`

#### Document Ingestion Flow (Google Drive Only)
1. OAuth2 authentication → `ingest/google_drive_ingester.py`
2. Comprehensive metadata extraction → File paths, permissions, owners
3. Document download and processing → Google Drive API
4. Content chunking and embedding → `bot/services/vector_service.py`
5. Vector storage with rich metadata → ChromaDB or Pinecone

#### Agent Processes
Defined in `bot/handlers/agent_processes.py` with the `AGENT_PROCESSES` dictionary. Users can trigger data processing jobs through natural language requests.

### Threading and Context
- Automatically creates and maintains Slack threads
- Retrieves thread history for context in LLM conversations
- Shows typing indicators during response generation
- Maintains online presence status

### RAG & LLM Integration

#### Supported LLM Providers
- **OpenAI**: GPT-4, GPT-3.5, with configurable models
- **Anthropic**: Claude 3 (Haiku, Sonnet, Opus)  
- **Ollama**: Local models (Llama 2, Code Llama, etc.)

#### Vector Database Options
- **ChromaDB**: Local or server deployment
- **Pinecone**: Cloud-hosted vector database

#### RAG Pipeline Features
- **Document Chunking**: Configurable size and overlap
- **Semantic Search**: Vector similarity with threshold filtering
- **Context Integration**: Retrieved chunks enhance LLM responses
- **Metadata Support**: Track document sources and properties
- **Configurable Retrieval**: Adjust chunk count and similarity thresholds

#### How It Works
1. **Ingestion**: Documents are chunked and embedded into vector database
2. **Query Processing**: User questions are embedded for similarity search
3. **Retrieval**: Most relevant chunks are retrieved based on similarity
4. **Augmentation**: Retrieved context is added to the LLM prompt
5. **Generation**: LLM generates response with enhanced context

## Testing Framework & Quality Standards

### Test Suite Requirements

**🎯 MANDATORY: All code changes MUST include comprehensive tests and pass 100% of the test suite.**

The project maintains a **155/155 test success rate (100%)** - this standard must be preserved.

#### Test Commands
```bash
# Run all tests (REQUIRED before any commit)
make test                    # Full test suite (155 tests)
make test-coverage          # Tests with coverage report (requires >70%, currently ~72%)
make test-file FILE=test_name.py  # Run specific test file

# Quality checks (REQUIRED before commit)  
make lint                   # Auto-fix with ruff + pyright + bandit (unified script)
make lint-check            # Check-only mode with ruff + pyright + bandit (unified script)
make typecheck             # Run pyright type checking only (legacy, use lint-check instead)
make quality               # Run complete pipeline: linting + type checking + tests

# Direct unified script usage (identical to CI behavior)
./scripts/lint.sh --fix     # Auto-fix mode: ruff format + ruff check --fix + pyright + bandit
./scripts/lint.sh           # Check mode: ruff format --check + ruff check + pyright + bandit
```

#### Pre-commit Requirements
```bash
# Setup (run once)
make setup-dev             # Install dev tools + pre-commit hooks

# Before every commit (MANDATORY)
make pre-commit           # Run all pre-commit hooks
git add . && git commit   # Hooks run automatically

# CI simulation
make ci                   # Run complete CI pipeline locally
```

### Testing Standards

#### 1. Test Coverage Requirements
- **Minimum 80% code coverage** (enforced by CI)
- **All new functions/classes MUST have tests**
- **Critical paths require 100% coverage**

#### 2. Test Types & Structure
```
bot/tests/
├── test_app.py              # Application initialization
├── test_config.py           # Configuration management  
├── test_conversation_cache.py  # Redis caching
├── test_event_handlers.py   # Slack event handling
├── test_formatting.py       # Message formatting
├── test_health_endpoints.py # Health check endpoints
├── test_integration.py      # End-to-end workflows
├── test_llm_service.py      # LLM API integration
├── test_message_handlers.py # Message processing
├── test_slack_service.py    # Slack API integration
└── test_utils.py            # Utilities and helpers

ingest/
└── tests/                   # Google Drive ingestion tests (future)
```

#### 3. Test Patterns (Follow These Examples)
```python
# ✅ GOOD: Async test with proper mocking
@pytest.mark.asyncio
async def test_message_handling_success(mock_slack_service):
    mock_slack_service.get_thread_history = AsyncMock(return_value=([], True))
    result = await handle_message("test", "U123", mock_slack_service, "C123")
    assert result is True
    mock_slack_service.send_message.assert_called_once()

# ✅ GOOD: Simple fixture for consistent mocking  
@pytest.fixture
def mock_service():
    service = AsyncMock(spec=ServiceClass)
    service.method.return_value = "expected_result"
    return service

# ❌ BAD: Complex async mocking that can hang tests
# Avoid deep nested AsyncMock patterns
```

### Code Quality Standards  

#### 1. Unified Quality Tooling (Auto-enforced)
- **Ruff**: Fast linting, formatting, and import sorting (replaces black + isort)
- **Pyright**: Type checking (strict mode, replaces MyPy for better performance)
- **Bandit**: Security vulnerability scanning

**🎯 Unified Script**: `./scripts/lint.sh` ensures identical behavior across:
- Local development (`make lint`, `make lint-check`)
- Pre-commit hooks (automatic on git commit)
- CI pipeline (GitHub Actions)

**Benefits**: Single modern toolchain, faster execution, zero conflicts between tools.

#### Consistency Guarantees
The unified `./scripts/lint.sh` script ensures **identical behavior** across all environments:

| Environment | Tools | Consistency |
|-------------|-------|-------------|
| Local dev (`make lint-check`) | Ruff + Pyright + Bandit | ✅ Same script |
| Pre-commit hooks | Ruff + Pyright + Bandit | ✅ Same script |
| CI pipeline | Ruff + Pyright + Bandit | ✅ Same script |

**No more "works locally but fails in CI"** - all environments use identical tooling and configuration.

#### 2. Type Annotations (Required)
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
   ```bash
   # Create test file for new feature
   touch bot/tests/test_new_feature.py
   # Write failing tests
   # Implement feature to make tests pass
   ```

2. **Maintain Existing Tests**
   ```bash
   # After code changes, ensure all tests still pass
   make test
   # Update tests if interfaces change
   # Never delete tests without replacement
   ```

3. **Run Quality Checks**
   ```bash
   # MANDATORY before every commit
   make quality              # All checks + tests
   make pre-commit          # Pre-commit hooks
   ```

4. **Commit with Verified Quality**
   ```bash
   # Only commit when all checks pass
   git add .
   git commit -m "feat: add new feature with comprehensive tests"
   git push
   ```

#### For Bug Fixes:

1. **Write Reproduction Test**
   ```python
   def test_bug_reproduction():
       """Test that reproduces the reported bug."""
       # This test should fail initially
       assert buggy_function() == expected_result
   ```

2. **Fix the Bug**
   ```python
   # Implement fix
   # Test should now pass
   ```

3. **Add Edge Case Tests**
   ```python
   def test_edge_cases():
       """Test edge cases related to the bug."""
       # Prevent regression
   ```

### Integration with CI/CD

#### GitHub Actions Pipeline
- **Triggered on**: Every push and PR
- **Runs**: `make ci` (quality + tests + build)
- **Blocks merge**: If any test fails or coverage < 70%

#### Test Coverage Requirements
- **Minimum Coverage**: 70% (enforced by CI)
- **Current Coverage**: ~72% (excluding CLI scripts)
- **Coverage Exclusions**: `bot/app.py`, `ingest/google_drive_ingester.py` (CLI scripts)
- **Coverage Command**: `make test-coverage`
- **Configuration**: `.coveragerc` with realistic production thresholds

#### Pre-commit Hooks (Local)
- **Unified Quality Checks**: Uses `./scripts/lint.sh` (same as CI)
- **Ruff**: Linting, formatting, and import sorting
- **Pyright**: Type checking with strict mode
- **Bandit**: Security vulnerability scanning
- **File cleanup**: Trailing whitespace, line endings, merge conflicts
- **Syntax validation**: Python AST, YAML, TOML, JSON

### Test Environment

#### Test Configuration
```bash
# Test Redis (optional, uses fakeredis if unavailable)  
CACHE_REDIS_URL=redis://localhost:6379/1

# Test environment file
cp bot/tests/.env.test .env.test
```

#### Test Data Management
- **Use fixtures for consistent test data**
- **Mock external services (Slack, LLM APIs)**
- **Clean up after tests (cache)**
- **Isolate tests (no shared state)**

### Performance Testing

```bash
# Monitor test performance
make test-coverage          # Includes timing
pytest --durations=10       # Show 10 slowest tests

# Keep tests fast (< 2 seconds per test)
# Use mocking instead of real API calls
```

This testing framework ensures **100% reliability** and **production-ready code quality**.

## Production Deployment

### Docker Deployment (Recommended)

```bash
# Build and run with Docker Compose
docker compose -f docker-compose.prod.yml up -d

# Or build Docker image directly
make docker-build
make docker-run
```

**Features:**
- Health checks on port 8080 (`/health`, `/ready`, `/metrics`)
- Automatic restart on failure
- Log rotation and persistent storage
- Resource limits (512M memory, 0.5 CPU)
- Graceful shutdown handling
- Container isolation and security

### Environment Variables

Required for production:
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token  
LLM_API_URL=https://your-api.com
LLM_API_KEY=your-api-key
```

Optional:
```bash
ENVIRONMENT=production          # Enables JSON logging
LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR
HEALTH_PORT=8080              # Health check server port
```

### Monitoring & Alerting

**Health Endpoints:**
- `GET /health` - Basic health check
- `GET /ready` - Readiness probe (checks LLM API)
- `GET /metrics` - Basic metrics

**Docker Monitoring:**
- Built-in health checks with Docker and Docker Compose
- Container auto-restart on failure
- Health check endpoints exposed on port 8080
- Use `docker logs slack-bot` to view application logs

**Logging:**
- Production: Structured JSON logs to stdout and files
- Development: Human-readable console logs
- Log rotation: 50MB files, 5 backups for main log, 10 for errors
- Third-party library logs suppressed

### Production Considerations

**Resource Requirements (100 users):**
- Memory: 256MB reserved, 512MB limit
- CPU: 0.25 cores reserved, 0.5 limit
- Disk: ~100MB for application, variable for logs

**Security:**
- Runs as non-root user
- Container security hardening
- Environment variable protection

**Reliability:**
- Graceful shutdown on SIGTERM/SIGINT
- Auto-restart on crashes
- Health check integration with orchestrators
- Connection recovery for network issues

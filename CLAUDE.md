# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

### Database Migrations
```bash
cd src && python migrate.py status    # Show migration status
cd src && python migrate.py migrate   # Apply pending migrations
cd src && python migrate.py rollback 001  # Rollback specific migration
```

### Utilities
```bash
make clean        # Remove caches and build artifacts
```

## Environment Configuration

The application requires a `.env` file in the project root with:
```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
LLM_API_URL=http://your-llm-api-url
LLM_API_KEY=your-llm-api-key
LLM_MODEL=gpt-4o-mini
```

## Architecture Overview

This is a Python-based Slack bot for Insight Mesh that integrates with LLM APIs for RAG functionality and agent processes.

### Core Structure
- **src/app.py**: Main application entry point with async Socket Mode handler
- **src/config/**: Pydantic settings with environment-based configuration
- **src/handlers/**: Event and message handling, including agent process management
- **src/services/**: Core services for LLM API, Slack API, and message formatting
- **src/utils/**: Error handling and logging utilities

### Key Components

#### Settings Management (config/settings.py)
Uses Pydantic with environment variable prefixes:
- `SlackSettings` (SLACK_*)
- `LLMSettings` (LLM_*)  
- `AgentSettings` (AGENT_*)

#### Message Flow
1. Slack events → `handlers/event_handlers.py`
2. Message processing → `handlers/message_handlers.py`
3. LLM API calls → `services/llm_service.py`
4. Response formatting → `services/formatting.py`
5. Slack response → `services/slack_service.py`

#### Agent Processes
Defined in `handlers/agent_processes.py` with the `AGENT_PROCESSES` dictionary. Users can trigger data processing jobs through natural language requests.

### Threading and Context
- Automatically creates and maintains Slack threads
- Retrieves thread history for context in LLM conversations
- Shows typing indicators during response generation
- Maintains online presence status

### LLM Integration
- Compatible with OpenAI API format
- Sends user authentication tokens via headers and metadata
- Uses async HTTP client (aiohttp) for API calls
- Configurable model, temperature, and token limits

## Testing Framework & Quality Standards

### Test Suite Requirements

**🎯 MANDATORY: All code changes MUST include comprehensive tests and pass 100% of the test suite.**

The project maintains a **154/154 test success rate (100%)** - this standard must be preserved.

#### Test Commands
```bash
# Run all tests (REQUIRED before any commit)
make test                    # Full test suite with coverage
make test-coverage          # Tests with HTML coverage report  
make test-file FILE=test_name.py  # Run specific test file

# Quality checks (REQUIRED before commit)
make lint                   # Auto-fix linting issues
make lint-check            # Check linting without fixing
make typecheck             # Run mypy type checking
make quality               # Run all quality checks + tests
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
src/tests/
├── test_app.py              # Application initialization
├── test_config.py           # Configuration management  
├── test_conversation_cache.py  # Redis caching
├── test_event_handlers.py   # Slack event handling
├── test_formatting.py       # Message formatting
├── test_health_endpoints.py # Health check endpoints
├── test_integration.py      # End-to-end workflows
├── test_llm_service.py      # LLM API integration
├── test_message_handlers.py # Message processing
├── test_migrations.py       # Database migrations
├── test_prompt_commands.py  # User prompt commands
├── test_slack_service.py    # Slack API integration
├── test_user_prompt_service.py  # Database operations
└── test_utils.py           # Utilities and helpers
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

#### 1. Linting & Formatting (Auto-enforced)
- **Ruff**: Fast linting with auto-fix
- **Black**: Code formatting  
- **isort**: Import sorting
- **MyPy**: Type checking (strict mode)
- **Bandit**: Security scanning

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
   touch src/tests/test_new_feature.py
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
- **Blocks merge**: If any test fails or coverage < 80%

#### Pre-commit Hooks (Local)
- **Ruff linting** with auto-fix
- **Black formatting**  
- **Type checking**
- **Security scanning**
- **Test file validation**

### Test Environment

#### Test Configuration
```bash
# Test database (automatic setup)
DATABASE_URL=postgresql://test:test@localhost:5432/test_db

# Test Redis (optional, uses fakeredis if unavailable)  
CACHE_REDIS_URL=redis://localhost:6379/1

# Test environment file
cp src/tests/.env.test .env.test
```

#### Test Data Management
- **Use fixtures for consistent test data**
- **Mock external services (Slack, LLM APIs)**
- **Clean up after tests (database, cache)**
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

### Full Stack Deployment (Default)

```bash
# Deploy with complete monitoring stack (DEFAULT)
./deployment/deploy.sh

# Or explicitly specify monitoring
./deployment/deploy.sh monitoring
```

**Features:**
- Health checks on port 8080 (`/health`, `/ready`, `/metrics`)
- Automatic restart on failure
- Log rotation and persistent storage
- Resource limits (512M memory, 0.5 CPU)
- Graceful shutdown handling

### Alternative Deployments

```bash
# Basic bot only (lightweight)
./deployment/deploy.sh docker

# System service (no Docker)  
sudo ./deployment/deploy.sh systemd
```

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
- `GET /migrations` - Database migration status

**Automated Monitoring:**
```bash
# Set up monitoring cron job (every 5 minutes)
*/5 * * * * /path/to/monitoring_check.sh
```

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

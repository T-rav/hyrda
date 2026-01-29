# InsightMesh - AI Coding Agent Guide

This document provides essential information for AI coding agents working with the InsightMesh codebase.

## Project Overview

InsightMesh is a production-ready Slack AI Bot with **RAG (Retrieval-Augmented Generation)**, **Deep Research Agents**, and **Web Search** capabilities. It provides intelligent, context-aware assistance using knowledge bases and real-time web data.

### Key Capabilities

- **Advanced RAG Intelligence**: Qdrant vector search with hybrid retrieval, cross-encoder reranking, and adaptive query rewriting
- **Web Search & Real-Time Data**: Tavily web search and Perplexity deep research integration
- **Deep Research Agents**: Multi-agent LangGraph system for comprehensive company analysis
- **Production Ready**: Thread management, conversation summarization, health monitoring, and comprehensive observability

## Technology Stack

### Core Technologies

| Component | Technology |
|-----------|------------|
| Language | Python 3.11 |
| Slack Framework | slack-bolt |
| Agent Orchestration | LangChain / LangGraph |
| LLM Providers | OpenAI (GPT-4o), Anthropic (Claude) |
| Vector Database | Qdrant |
| Relational Database | MySQL 8.0 |
| Cache | Redis |
| Observability | Langfuse, Prometheus |
| Task Scheduling | Custom tasks service with APScheduler |

### External Integrations

- **Tavily**: Web search API
- **Perplexity**: Deep research with citations
- **Google Drive**: Document ingestion with OAuth2
- **Langfuse**: LLM observability and prompt management

## Architecture

### Microservices Architecture

The project consists of 6 microservices communicating via HTTP APIs:

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
┌─────────────────┐
│     Qdrant      │
│ (Vector Store)  │
└─────────────────┘
```

### Service Descriptions

| Service | Path | Purpose | Port |
|---------|------|---------|------|
| **Bot** | `bot/` | Slack event handling and message processing | 8080 |
| **Agent Service** | `agent-service/` | LangGraph HTTP API for deep research agents | 8000 |
| **Control Plane** | `control_plane/` | Agent registry, management UI, authentication | 6001 |
| **Tasks** | `tasks/` | Background task scheduler and Google Drive ingestion | 5001 |
| **RAG Service** | `rag-service/` | Vector search and knowledge base queries | 8002 |
| **Dashboard** | `dashboard-service/` | Health monitoring and metrics aggregation | (internal) |

### Shared Code

The `shared/` directory contains utilities used across services:
- `shared/clients/` - HTTP clients for inter-service communication
- `shared/config/` - Common configuration
- `shared/middleware/` - Authentication and logging middleware
- `shared/services/` - Shared service utilities
- `shared/tools/` - Common tool implementations
- `shared/utils/` - Helper utilities including OpenTelemetry tracing

## Project Structure

```
insightmesh/
├── bot/                          # Main Slack bot service
│   ├── app.py                    # Application entry point
│   ├── health.py                 # Health check endpoints
│   ├── config/                   # Pydantic settings
│   │   └── settings.py           # Environment configuration
│   ├── handlers/                 # Event handling
│   │   ├── event_handlers.py     # Slack event handlers
│   │   └── message_handlers.py   # Message processing logic
│   ├── services/                 # Core services
│   │   ├── llm_service.py        # LLM interaction
│   │   ├── rag_client.py         # RAG service client
│   │   ├── agent_client.py       # Agent service client
│   │   ├── conversation_cache.py # Redis conversation storage
│   │   └── search_clients.py     # Tavily/Perplexity clients
│   ├── utils/                    # Utilities
│   └── tests/                    # Test suite (245 tests)
├── agent-service/                # LangGraph HTTP API
│   ├── agents/                   # Agent implementations
│   ├── api/                      # FastAPI routes
│   └── services/                 # Agent services
├── control_plane/                # Agent registry & management
│   ├── api/                      # REST API endpoints
│   ├── ui/                       # Web UI
│   └── models/                   # Database models
├── tasks/                        # Background task scheduler
│   ├── jobs/                     # Job implementations
│   ├── ui/                       # React frontend
│   └── services/                 # Task services
├── rag-service/                  # Vector search service
│   ├── services/                 # Retrieval services
│   └── vector_stores/            # Qdrant integration
├── dashboard-service/            # Health monitoring
│   ├── health_aggregator.py      # Service health aggregation
│   └── health_ui/                # React health dashboard
├── shared/                       # Shared utilities
├── custom_agents/                # Custom agent definitions
├── external_agents/              # External agent configurations
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
└── monitoring/                   # Prometheus/Grafana configs
```

## Build and Development Commands

### Essential Make Commands

```bash
# PRIMARY COMMAND - Comprehensive validation
make ci                    # Run lint + test + security + build

# Development
make install              # Install Python dependencies
make setup-dev            # Install dev tools + pre-commit hooks
make run                  # Run bot locally (requires .env)

# Testing
make test                 # Run all 6 microservices tests
make test-fast            # Unit tests only (excludes integration)
make test-coverage        # Tests with coverage report (>70% required)

# Code Quality
make lint                 # Auto-fix linting, formatting, imports
make lint-check           # Check-only mode (used by pre-commit)
make quality              # Complete pipeline: lint + type check + test

# Docker Operations
make start                # Start full Docker stack
make stop                 # Stop all containers
make restart              # Restart all services
make status               # Show container status
make docker-build         # Build all Docker images

# Security
make security             # Run Bandit code security scanner
make security-docker      # Scan Docker images with Trivy
make security-full        # Run both Bandit + Trivy

# Database
make db-start             # Start MySQL databases
make db-stop              # Stop MySQL databases
make db-migrate           # Generate new migration files
make db-upgrade           # Apply pending migrations
make db-downgrade         # Rollback last migration
```

### Docker Compose Commands

```bash
# Full stack deployment
docker compose up -d                    # Start all services
docker compose down                     # Stop all services
docker compose logs -f bot              # View bot logs
docker compose ps                       # Check service status

# Individual services
docker compose up -d qdrant            # Start Qdrant only
docker compose restart bot             # Restart bot after code changes
```

## Code Style Guidelines

### Quality Tooling

The project uses unified quality tooling across local dev, pre-commit, and CI:

| Tool | Purpose | Config |
|------|---------|--------|
| **Ruff** | Linting, formatting, import sorting | `bot/pyproject.toml` |
| **Pyright** | Type checking (strict mode) | `bot/pyproject.toml` |
| **Bandit** | Security vulnerability scanning | `bot/pyproject.toml` |

### Type Annotations (Required)

All functions must have type hints:

```python
# ✅ REQUIRED
async def process_message(
    text: str,
    user_id: str,
    service: SlackService
) -> bool:
    """Process a message with proper typing."""
    return True

# ❌ FORBIDDEN - Untyped functions
def process_message(text, user_id, service):
    return True
```

### Ruff Configuration

- Target Python version: 3.11
- Line length: 88 characters
- Quote style: double
- Import sorting enabled (isort)

See `bot/pyproject.toml` for complete configuration.

## Testing Instructions

### Testing Requirements

**MANDATORY**: All code changes MUST include comprehensive tests and pass 100% of the test suite.

- ✅ New features: Write tests BEFORE committing
- ✅ Bug fixes: Add regression tests
- ✅ Refactoring: Ensure existing tests pass
- ✅ API changes: Test all endpoints and error cases

### Test Commands by Service

```bash
# Bot service
cd bot && PYTHONPATH=. pytest tests/ -v

# Agent service
cd agent-service && PYTHONPATH=. pytest tests/ -v

# Control plane
cd control_plane && PYTHONPATH=. pytest tests/ -v

# Tasks service
cd tasks && PYTHONPATH=. pytest -m "not integration" tests/ -v

# RAG service
cd rag-service && PYTHONPATH=.. pytest tests/ -v

# Dashboard service
cd dashboard-service && PYTHONPATH=.. pytest tests/ -v
```

### Test Markers

```bash
# Run only unit tests (fast)
pytest -m "not integration and not slow"

# Run only integration tests
pytest -m integration

# Run tests matching a pattern
pytest -k "test_auth"
```

### Coverage Requirements

- **Minimum Coverage**: 70% (enforced by CI)
- All new functions/classes MUST have tests
- Critical paths require 100% coverage

## Security Considerations

### Security Standards

InsightMesh follows the 8th Light Host Hardening Policy:

- **Secrets Management**: Never commit secrets (`.env` in `.gitignore`)
- **Container Security**: All containers run as non-root user (UID 1000)
- **Code Scanning**: 50+ Bandit security checks
- **Docker Scanning**: Trivy scans for CVEs and secrets
- **Service Authentication**: Inter-service tokens required

### Pre-commit Security Checks

```bash
# Run all quality checks before committing
make lint                 # Auto-fix issues
make test                 # Ensure tests pass

# Never skip commit hooks
# ❌ NEVER USE: git commit --no-verify
```

### Service-to-Service Authentication

All inter-service requests require authentication tokens:

```python
# Headers required for service calls
headers = {
    "X-Service-Token": settings.service_token,
    "X-Request-ID": generate_request_id()
}
```

### Security Commands

```bash
# Code security scan
make security

# Docker image scan
make security-docker

# Full security audit
make security-full
```

## Environment Configuration

### Required Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Slack (required)
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# LLM Provider (required)
LLM_API_KEY=sk-your-openai-api-key
LLM_MODEL=gpt-4o-mini

# Database (required)
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/bot

# Cache (optional, defaults to localhost)
CACHE_REDIS_URL=redis://localhost:6379

# Vector Database (optional, defaults to localhost)
VECTOR_HOST=localhost
VECTOR_PORT=6333
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base

# Web Search (optional)
TAVILY_API_KEY=your-tavily-api-key
PERPLEXITY_API_KEY=your-perplexity-api-key

# Observability (optional)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-your-key
LANGFUSE_SECRET_KEY=sk-lf-your-key
```

### Google Drive Ingestion Setup

```bash
# 1. Configure OAuth credentials in .env
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
SERVER_BASE_URL=http://localhost:5001
OAUTH_ENCRYPTION_KEY=your-fernet-key

# 2. Authenticate (saves credential to database)
open http://localhost:5001/api/gdrive/auth

# 3. Create scheduled ingestion job via web UI
open http://localhost:5001
```

## CI/CD Pipeline

### GitHub Actions Workflows

| Workflow | File | Purpose |
|----------|------|---------|
| CI Pipeline | `.github/workflows/test.yml` | Lint, test, build, Docker security scan |
| Quality Gate | `.github/workflows/quality-gate.yml` | Claude Code audit (disabled) |

### CI Pipeline Stages

1. **Python Tests** (tasks service)
2. **React Tests** (tasks UI)
3. **LibreChat Build**
4. **Docker Security Scanning** (Trivy)

### Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:

- Unified lint check (Ruff + Pyright + Bandit via Makefile)
- React UI linting and tests
- Trailing whitespace removal
- YAML/TOML/JSON syntax validation
- Large file check

## Common Development Tasks

### Adding a New Service

1. Create directory with `pyproject.toml`, `Dockerfile`, `app.py`
2. Add service to `docker-compose.yml`
3. Add health check endpoint
4. Add tests to `tests/` directory
5. Update Makefile with service-specific targets
6. Add to `make ci` pipeline

### Adding a New Agent

1. Create agent in `agent-service/agents/` or `custom_agents/`
2. Define graph builder function
3. Add entry to `langgraph.json` graphs
4. Register agent with control plane
5. Add comprehensive tests

### Database Migrations

```bash
# Generate migration
cd <service> && alembic revision --autogenerate -m "description"

# Apply migrations
cd <service> && alembic upgrade head

# Check status
make db-status
```

## Debugging and Monitoring

### Health Dashboard

Access at `http://localhost:8080/ui`:
- Real-time service status
- System metrics (memory, uptime)
- Error information and troubleshooting

### Langfuse Observability

- Cost tracking per user/conversation
- Performance analytics
- Conversation traces
- Prompt versioning

### Logs

```bash
# View all service logs
docker compose logs -f

# View specific service
docker compose logs -f bot
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `Makefile` | Build automation and common commands |
| `docker-compose.yml` | Service orchestration |
| `bot/pyproject.toml` | Python dependencies and tool config |
| `.env.example` | Environment variable template |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `langgraph.json` | LangGraph agent definitions |
| `CLAUDE.md` | Detailed development workflow |

## Getting Help

- **README.md**: Comprehensive project documentation
- **CLAUDE.md**: Detailed development workflow and standards
- **docs/**: Additional documentation (Langfuse setup, security, etc.)
- **Service READMEs**: Each service has its own README.md

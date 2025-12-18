# InsightMesh Slack AI Bot

**Version 1.1.0** - HTTP-Based Agent Architecture

A production-ready Slack bot with **RAG (Retrieval-Augmented Generation)**, **Deep Research Agents**, and **Web Search** capabilities that provides intelligent, context-aware assistance using your own knowledge base and real-time web data.

## 🆕 What's New in v1.1.0

### Latest Updates (December 2024)
- **LangGraph Agent Integration**: Fixed agent invocation for LangGraph CompiledStateGraph instances
  - Agents now properly detected and invoked with correct method signatures
  - Support for both traditional agents and LangGraph graph-based agents
- **Enhanced Testing**: All 3,302 tests passing across all services
  - Comprehensive RBAC integration test coverage
  - Fixed authentication test suite
  - Control plane agent registration tests
- **Profile Agent Improvements**: Added fallback prompts for development/testing environments
  - Graceful degradation when Langfuse unavailable
  - Proper PromptService initialization

### Architecture Improvements
- **Microservices Architecture**: Agents extracted to separate HTTP-based service for better scalability
- **Agent Service**: FastAPI-based service for specialized AI agents (Profile, MEDDIC, Help)
- **Control Plane**: New web-based management UI for agent permissions and user access
  - Agent registry viewer and permission management
  - Full RBAC implementation with group-based permissions
  - Audit logs and usage analytics

### Benefits
- **Better Scalability**: Independent scaling of bot and agent services
- **Easier Extensibility**: Add new agents without modifying bot code
- **Centralized Management**: Control plane for permissions and access control
- **Production Ready**: Clean separation of concerns and service boundaries

## ✨ Features

### 🧠 **Advanced RAG Intelligence**
- **Qdrant Vector Search**: Fast, self-hosted semantic search with dense embeddings
- **Hybrid Retrieval**: Dense + sparse retrieval with Reciprocal Rank Fusion (RRF)
- **Cross-Encoder Reranking**: Cohere reranking for improved result relevance
- **Adaptive Query Rewriting**: Automatically rewrites user queries for better retrieval accuracy
- **Smart Diversification**: Returns chunks from multiple documents for comprehensive context
- **Source Attribution**: Shows which documents informed each response
- **Internal Deep Research**: Multi-query RAG with compression for in-depth knowledge base exploration

### 🌐 **Web Search & Real-Time Data**
- **Tavily Web Search**: Fast web search integration with Tavily API
- **Perplexity Deep Research**: Long-form research reports with citations (5-15 minute tasks)
- **Smart URL Scraping**: Extract content from web pages with automatic fallback
- **Function Calling**: LLM automatically decides when to search the web vs use knowledge base

### 🔬 **Deep Research Agents (LangGraph)**
- **Company Profile Researcher**: Multi-agent system for comprehensive company analysis
- **Supervisor-Researcher Architecture**: Parallel research execution with compression
- **Research Brief Generation**: Structured research plans from natural language queries
- **Final Report Synthesis**: Professional, well-cited reports with PDF export
- **LangGraph Studio Support**: Visual debugging and development via `langgraph dev`

### 🔧 **Production Ready**
- **Thread Management**: Automatically manages conversation threads and context
- **Conversation Summarization**: Sliding window with smart summarization at 75% context threshold
- **Typing Indicators**: Shows typing states while generating responses
- **Online Presence**: Shows as "online" with a green status indicator
- **Health Dashboard**: Real-time monitoring UI at `http://localhost:8080/ui`
- **LLM Observability**: Langfuse integration for tracing, analytics, and cost monitoring
- **Prometheus Metrics**: Native metrics collection for infrastructure monitoring

### 🚀 **Easy Setup & Deployment**
- **No Proxy Required**: Direct API integration eliminates infrastructure complexity
- **Docker Compose**: Full stack deployment (bot + Qdrant + Redis + MySQL + Tasks Service)
- **Scheduled Document Ingestion**: OAuth2-based Google Drive ingestion via tasks service (replaces CLI)
- **Multiple LLM Providers**: OpenAI, Anthropic, or Ollama support
- **Flexible Configuration**: Environment-based settings with sensible defaults

## 🚀 Quick Start

**Requirements:** Python 3.11+, Docker (for services)

### 1. **Clone and Configure**
```bash
git clone https://github.com/8thlight/insightmesh.git
cd insightmesh

# Copy example configuration
cp .env.example .env
```

### 2. **Set Up Your Environment**
Edit `.env` with your credentials:

```bash
# Slack (get from https://api.slack.com/apps)
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# OpenAI (get from https://platform.openai.com/api-keys)
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-api-key
LLM_MODEL=gpt-4o-mini

# Qdrant Vector Database (runs in Docker)
VECTOR_PROVIDER=qdrant
VECTOR_HOST=localhost  # Use 'qdrant' in Docker
VECTOR_PORT=6333
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base

# Web Search Configuration
TAVILY_API_KEY=your-tavily-api-key  # Get from https://tavily.com

# Perplexity for deep research (optional, recommended)
PERPLEXITY_API_KEY=your-perplexity-api-key  # Get from https://www.perplexity.ai/settings/api

# Database for user prompts and tasks
DATABASE_URL=mysql+pymysql://insightmesh_bot:insightmesh_bot_password@localhost:3306/bot

# Optional: Langfuse observability
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk_lf_your_public_key_here
LANGFUSE_SECRET_KEY=sk_lf_your_secret_key_here
```

### 3. **Start Services with Docker Compose**
```bash
# Start full stack: bot + Qdrant + Redis + MySQL
docker compose up -d

# Check status
docker compose ps

# View logs
docker logs -f insightmesh-bot
```

### 4. **Set Up Document Ingestion (via Tasks Service)**

**Workflow**: Update .env → Authenticate → Create Scheduled Task

```bash
# Step 1: Update .env with Google OAuth credentials (from Google Cloud Console)
# Add these to your .env file:
#   GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
#   GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
#   SERVER_BASE_URL=http://localhost:5001
#   OAUTH_ENCRYPTION_KEY=your-fernet-key

# Step 2: Start services and authenticate Google Drive
docker compose up -d

# Visit OAuth URL to grant permissions (saves credential to database):
open http://localhost:5001/api/gdrive/auth
# - Grant Google Drive permissions in OAuth popup
# - Success page appears and auto-closes after 3 seconds
# - Credential saved with ID (e.g., "prod_gdrive")

# Step 3: Create scheduled ingestion job in web UI
open http://localhost:5001
# In the tasks dashboard:
#   - Job Type: "Google Drive Ingestion"
#   - Credential ID: "prod_gdrive" (from step 2)
#   - Folder ID: "0AMXFYdnvxhbpUk9PVA" (production documents folder)
#   - Schedule: Daily at 3 AM (or your preferred schedule)
```

**Supported Formats**: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Google Workspace files

### 5. **Test Your Bot**
Message your bot in Slack:
- "What is our refund policy?" (uses knowledge base)
- "What's the latest news about AI?" (uses web search)
- "Research Tesla's AI strategy" (triggers deep research agent)

That's it! Your RAG-enabled Slack bot with deep research capabilities is now running. 🎉

## 📊 Development Commands

### Setup and Installation
```bash
make install      # Install Python dependencies
make setup-dev    # Install dev tools + pre-commit hooks
```

### Running the Application
```bash
make run          # Run the Slack bot (requires .env file)

# Or with Docker
docker compose up -d
docker logs -f insightmesh-bot
```

### Code Quality
```bash
make lint         # Auto-fix linting and formatting
make quality      # Run complete quality pipeline
make test         # Run test suite
```

### Pre-commit and CI
```bash
make pre-commit   # Run all pre-commit hooks
make ci           # Run complete CI pipeline locally
```

### Docker Operations
```bash
# Full stack
docker compose up -d              # Start all services
docker compose down               # Stop all services
docker compose logs -f bot        # View bot logs

# Individual services
docker compose up -d qdrant       # Start Qdrant only
docker compose restart bot        # Restart bot after code changes

# Build and run
make docker-build                 # Build Docker images
make docker-run                   # Run Docker container with .env
```

### Document Ingestion (Tasks Service)
```bash
# PRODUCTION METHOD: Web UI-based scheduled ingestion

# 1. Authenticate Google Drive FIRST (opens OAuth flow)
open http://localhost:5001/api/gdrive/auth

# 2. Create scheduled job in web UI
open http://localhost:5001
# - Job Type: Google Drive Ingestion
# - Credential ID: From step 1 (e.g., "prod_gdrive")
# - Folder ID: "0AMXFYdnvxhbpUk9PVA" (production folder)
# - Schedule: Daily at 3 AM or your preferred schedule

# Prerequisites in .env:
# GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
# GOOGLE_OAUTH_CLIENT_SECRET=your-secret
# SERVER_BASE_URL=http://localhost:5001 (must match Google Cloud Console)
```

## 🔧 Qdrant Setup

Qdrant runs automatically in Docker Compose. No manual setup required!

### Manual Collection Creation (Optional)

If you need to create collections manually:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="insightmesh-knowledge-base",
    vectors_config=VectorParams(
        size=1536,  # text-embedding-3-small dimension
        distance=Distance.COSINE
    )
)
```

### Qdrant Configuration

```bash
# Required settings in .env
VECTOR_PROVIDER=qdrant
VECTOR_HOST=localhost  # Use 'qdrant' when bot runs in Docker
VECTOR_PORT=6333
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base

# Embedding model (must match collection dimension)
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small  # 1536 dimensions
```

### Qdrant Web UI

Access the Qdrant dashboard at `http://localhost:6333/dashboard` to:
- View collections and vectors
- Monitor search performance
- Debug retrieval issues

## 🌐 Web Search Configuration

The bot includes direct integration with Tavily and Perplexity for web search and deep research.

### Features
- **Tavily Web Search**: Fast, high-quality web search results
- **Perplexity Deep Research**: 5-15 minute long-form research with citations
- **Smart URL Scraping**: Extract clean content from web pages
- **Function Calling**: LLM decides when to search vs use knowledge base

### Configuration

```bash
# In .env
# Web search via Tavily
TAVILY_API_KEY=your-tavily-api-key  # Get from https://tavily.com

# Deep research (optional but recommended)
PERPLEXITY_API_KEY=your-perplexity-key  # Get from https://www.perplexity.ai/settings/api
```

## 🔬 Deep Research Agents

The bot includes a multi-agent deep research system built with LangGraph for comprehensive company analysis.

### Features
- **Natural Language Queries**: "Research Tesla's AI strategy" → structured research plan → parallel execution
- **Supervisor-Researcher Architecture**: 1 supervisor delegates to 3 concurrent researchers
- **Web + Knowledge Base**: Combines internal docs with real-time web data
- **Research Compression**: Summarizes findings at each stage to manage context
- **Professional Reports**: Well-cited markdown reports with optional PDF export

### How to Use

In Slack, ask the bot to research a company:
```
Research Tesla's AI initiatives and competitive positioning
```

The bot will:
1. **Clarify** (optional): Ask follow-up questions if query is ambiguous
2. **Plan**: Generate a structured research brief with focused questions
3. **Execute**: Launch 3 parallel researchers with web search + deep research tools
4. **Compress**: Summarize findings from each researcher
5. **Synthesize**: Generate final professional report with citations

### Configuration

```bash
# Deep research agent settings (optional overrides)
MAX_RESEARCHER_ITERATIONS=8         # Supervisor reflection cycles
MAX_REACT_TOOL_CALLS=15            # Max tool calls per researcher
MAX_CONCURRENT_RESEARCH_UNITS=3    # Parallel researchers

# Token limits for deep research workflow
RESEARCH_MODEL_MAX_TOKENS=16000       # Researcher tool calling
COMPRESSION_MODEL_MAX_TOKENS=8000     # Compression output per researcher
FINAL_REPORT_MODEL_MAX_TOKENS=32000   # Final report generation

# PDF export styling
PDF_STYLE=professional  # Options: minimal, professional, detailed
```

### LangGraph Studio

Debug and visualize the research agent with LangGraph Studio:

```bash
# Start LangGraph dev server
langgraph dev

# Or with Docker
docker compose -f docker-compose.dev.yml up -d langgraph-studio
```

Access at `http://localhost:8123` - See `LANGGRAPH_STUDIO.md` for details.

## 🏗️ Architecture

### Technology Stack

- **slack-bolt**: Slack's official Python framework
- **LangChain/LangGraph**: Agent orchestration and workflows
- **FastAPI**: HTTP API for agent-service
- **OpenAI/Anthropic**: LLM providers (GPT-4o, Claude)
- **Qdrant**: Self-hosted vector database
- **Tavily & Perplexity**: Direct web search and deep research integration
- **MySQL**: Database for user prompts, tasks, and metrics
- **Redis**: Conversation caching and session management
- **Langfuse**: LLM observability and prompt management
- **Docker Compose**: Service orchestration

### Service Architecture

The application uses a **microservices architecture** with HTTP-based communication:

- **bot**: Slack integration and conversation management (Python/slack-bolt)
  - Port 8080: Health dashboard and metrics
- **agent-service**: Specialized AI agents via HTTP API (Python/FastAPI)
  - Profile agent: Company research and profiling
  - MEDDIC agent: Sales methodology coaching
  - Help agent: Onboarding and assistance
- **control-plane**: Agent permissions and user management (Flask + React)
  - Port 6001: Flask API backend
  - Port 6002: React frontend (dev mode)
  - Features: Agent registry, permission management, audit logs (coming soon)
- **tasks**: Background job scheduler with web UI
  - Port 5001: Task management and Google Drive ingestion
- **qdrant**: Vector database for semantic search
- **redis**: Conversation caching
- **mysql**: Data persistence

**Benefits of v1.1.0 Architecture:**
- Independent scaling of bot and agent services
- Better fault isolation and service boundaries
- Easier to add new agents
- Centralized governance via control plane

### Project Structure

```
bot/                              # Slack bot service
├── config/                       # Configuration management
│   └── settings.py               # Pydantic settings for LLM, RAG, etc.
├── handlers/                     # Event handling
│   ├── event_handlers.py         # Slack event handlers
│   ├── message_handlers.py       # Message handling logic
│   └── agent_processes.py        # Agent process management
├── services/                     # Core services
│   ├── agent_client.py           # HTTP client for agent-service
│   ├── agent_registry.py         # Agent routing and metadata
│   ├── search_clients.py         # Web search clients (Tavily, Perplexity)
│   ├── internal_deep_research.py # Internal knowledge base deep research
│   ├── conversation_manager.py   # Conversation context management
│   ├── llm_service.py            # RAG-enabled LLM service
│   ├── rag_service.py            # RAG orchestration and retrieval
│   ├── retrieval_service.py      # Retrieval coordination
│   ├── vector_service.py         # Qdrant integration
│   ├── embedding_service.py      # Text embedding generation
│   ├── langfuse_service.py       # Observability and tracing
│   └── slack_service.py          # Slack API integration
├── tests/                        # Comprehensive test suite
├── utils/                        # Utilities
│   ├── pdf_generator.py          # PDF report generation
│   └── errors.py                 # Error handling
├── app.py                        # Main application entry point
└── health.py                     # Health check endpoints

agent-service/                    # Agent service (HTTP API) [NEW in v1.1.0]
├── agents/                       # Specialized AI agents
│   ├── profiler/                 # Company profiler agent (LangGraph)
│   │   ├── nodes/                # Graph nodes: supervisor, researcher, compression
│   │   ├── state.py              # State definitions
│   │   └── prompts.py            # LLM prompts
│   └── meddpicc_coach/           # MEDDPICC coaching agent
├── tests/                        # Agent-specific tests
└── app.py                        # FastAPI application

control-plane/                    # Management UI [NEW in v1.1.0]
├── api/                          # Flask API backend
├── models/                       # Data models
├── services/                     # Business logic
├── ui/                           # React frontend
│   ├── src/                      # React components
│   └── public/                   # Static assets
├── app.py                        # Flask application
└── README.md                     # Control plane docs

tasks/                            # Background task scheduler (port 5001)
                                  # Handles Google Drive ingestion via OAuth2
evals/                            # LLM evaluation framework
```

### Core Workflows

#### RAG Pipeline
1. **Document Ingestion**: Google Drive → chunking → embedding → Qdrant storage
2. **Query Processing**: User question → adaptive query rewriting → embedding
3. **Retrieval**: Hybrid dense + sparse search with RRF fusion
4. **Reranking**: Cohere cross-encoder reranking (optional)
5. **Augmentation**: Retrieved context added to LLM prompt
6. **Generation**: LLM generates response with enhanced context
7. **Citation**: Source documents included in response

#### Deep Research Agent Flow
1. **Clarification**: Check if query needs clarification (optional)
2. **Research Brief**: Generate structured plan with focused questions
3. **Supervisor**: Delegate research tasks to parallel researchers
4. **Researchers**: Execute web_search, deep_research, scrape_url, internal_search
5. **Compression**: Summarize findings to manage context
6. **Final Report**: Synthesize comprehensive, well-cited report

#### Conversation Management
1. **Sliding Window**: Keep last 20 messages in context
2. **Summarization Trigger**: At 75% of model context window
3. **Smart Compression**: Keep 4 most recent messages + summary of older messages
4. **Cache**: Redis caching for fast retrieval

## 📱 Slack Integration

### Thread-Based Conversations
The bot automatically creates and maintains threads for organized discussions.

### Typing Indicators
Shows when the bot is "thinking" while generating responses.

### Universal Thread Response
The bot responds to any message in a thread it's part of, without requiring explicit mentions.

### Channel and Thread Support
- **Direct Messages (DMs)**: Always responds to all messages
- **Group Direct Messages**: Requires `mpim:history` permission
- **Private Channels**: Requires `groups:history` permission
- **Public Channels**: Requires `channels:history` permission

In all non-DM contexts, the bot:
- Responds to any message that directly @mentions it
- Automatically responds to all subsequent messages in that thread
- No need to @mention again for follow-ups in the same thread

### Online Status
The bot maintains an online presence with a green status indicator.

### Required Scopes

See "Slack App Setup Guide" section below for complete OAuth scope configuration.

## 🔐 Slack App Setup Guide

### Step 1: Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name your app (e.g., "InsightMesh")
4. Select your workspace

### Step 2: Configure OAuth Scopes

Navigate to "OAuth & Permissions" and add these **Bot Token Scopes**:

```
app_mentions:read       # Read mentions
chat:write              # Send messages
chat:write.customize    # Customize messages
chat:write.public       # Send to channels app isn't in
im:history              # View DM messages
im:read                 # View DM info
im:write                # Send DMs
mpim:history            # View group DM messages
groups:history          # View private channel messages
channels:history        # View public channel messages
channels:read           # View channel info
users:read              # View users
users:write             # Set presence status
commands                # Add slash commands
reactions:write         # Add reactions
files:write             # Upload files
```

### Step 3: Enable Socket Mode

1. Navigate to "Socket Mode"
2. Toggle on "Enable Socket Mode"
3. Create app-level token with `connections:write` scope
4. Save the token (starts with `xapp-`) for your `.env`

### Step 4: Configure Event Subscriptions

Navigate to "Event Subscriptions" and add:

```
app_mention         # App mentions
message.im          # Direct messages
message.mpim        # Group DMs
message.groups      # Private channels
message.channels    # Public channels
```

**Important**: Reinstall your app after adding events!

### Step 5: Disable App Home

1. Navigate to "App Home"
2. Toggle OFF "Home Tab"
3. Toggle ON "Allow users to send messages in app home"

### Step 6: Configure Interactivity

1. Navigate to "Interactivity & Shortcuts"
2. Toggle on "Interactivity"
3. Leave Request URL blank for Socket Mode

### Step 7: Install App

1. Navigate to "Install App"
2. Click "Install to Workspace"
3. Review permissions and click "Allow"
4. Copy the Bot User OAuth Token (starts with `xoxb-`) for your `.env`

## 📊 Monitoring & Observability

### Health Dashboard

Access at `http://localhost:8080/ui`:
- **Real-time status** of all services (LLM, Qdrant, Langfuse, WebCat, etc.)
- **System metrics**: Memory usage, active conversations, uptime
- **Error handling**: Detailed troubleshooting information
- **Auto-refresh**: Updates every 10 seconds

### Prometheus Metrics

Metrics endpoint at `http://localhost:8080/api/prometheus`:
- **Grafana-compatible** metrics
- **Active conversation tracking**
- **Performance metrics**

### Langfuse Observability

- **Cost tracking** per user, conversation, and model
- **Performance analytics** and prompt optimization
- **Conversation analytics** and user behavior patterns
- **Error tracking** with detailed LLM debugging
- **Prompt management**: Store and version system prompts
- **Query rewriting traces**: See how queries are rewritten
- **Agent traces**: Visualize deep research agent execution

See `docs/LANGFUSE_SETUP.md` for complete setup instructions.

## 🚨 Important Notes

### Document Ingestion
Google Drive ingestion is handled via **scheduled tasks** in the tasks service:

1. **Authenticate first**: Visit `http://localhost:5001/api/gdrive/auth` and grant permissions
2. **Create scheduled job**: In web UI at `http://localhost:5001`, set up ingestion task
3. **Production folder**: Use folder ID `0AMXFYdnvxhbpUk9PVA`

Requires Google OAuth2 credentials configured in `.env`. See `CLAUDE.md` for detailed workflow.

## 🔧 Troubleshooting

### Slack Issues
- **Bot not responding**: Check OAuth scopes and event subscriptions
- **Thread responses missing**: Verify `channels:history`, `groups:history`, etc. scopes
- **Mentions not working**: Reinstall app after adding scopes

### Environment Variables
- **Missing .env values**: Compare `.env` with `.env.example`
- **API key errors**: Test keys with provider's playground/console
- **Database connection**: Ensure MySQL is running via `docker compose ps`

### Services Not Starting
```bash
# Check service status
docker compose ps

# View logs
docker logs -f insightmesh-bot
docker logs -f insightmesh-qdrant

# Restart services
docker compose restart bot
```

### Qdrant Issues
- **Collection not found**: Collections are auto-created on first document ingestion via tasks service
- **Wrong dimensions**: Ensure embedding model matches collection (1536 for text-embedding-3-small)
- **Connection errors**: Check `VECTOR_HOST` is `localhost` locally or `qdrant` in Docker

### Web Search Issues
- **Search not working**: Check `TAVILY_API_KEY` is set and valid
- **Deep research failing**: Verify `PERPLEXITY_API_KEY` is set

### RAG Issues
- **No relevant results**: Check similarity thresholds in `.env` (try lowering `RAG_SIMILARITY_THRESHOLD`)
- **Query rewriting errors**: Disable with `RAG_ENABLE_QUERY_REWRITING=false`
- **Empty responses**: Verify documents are ingested (`docker logs insightmesh-qdrant`)

### Agent Issues
- **Recursion limit errors**: Should be fixed with limit of 100, check logs for actual issue
- **Agent stuck**: Check `max_react_tool_calls` and `max_researcher_iterations` limits
- **PDF generation failing**: Install `markdown` package: `pip install markdown`

### Debugging
- **Health dashboard**: Check `http://localhost:8080/ui` for service status
- **Langfuse traces**: View detailed execution in Langfuse dashboard
- **Bot logs**: `docker logs -f insightmesh-bot` for real-time debugging
- **Pre-commit failures**: Run `make lint` to auto-fix, then commit again

## 📚 Additional Documentation

- **CLAUDE.md**: Complete development workflow and coding standards
- **DEEP_RESEARCH_TRANSFER_GUIDE.md**: Deep research agent architecture and implementation
- **LANGGRAPH_STUDIO.md**: LangGraph Studio setup and debugging
- **control_plane/README.md**: Control plane setup and API documentation
- **docs/LANGFUSE_SETUP.md**: Langfuse observability setup
- **evals/README.md**: LLM evaluation framework

## 🎯 Production Deployment

### Docker Deployment (Recommended)

```bash
# Build and start all services
docker compose up -d

# View status
docker compose ps

# View logs
docker logs -f insightmesh-bot
```

### Environment Variables for Production

Update `.env` for production:
```bash
# Set to production
DEBUG=false
LOG_LEVEL=INFO

# Use Docker service names
VECTOR_HOST=qdrant
CACHE_REDIS_URL=redis://redis:6379

# Database with strong password
DATABASE_URL=mysql+pymysql://user:strong_password@mysql:3306/bot
```

### Resource Requirements

Minimum for 100 users:
- **Memory**: 2GB (bot) + 1GB (Qdrant)
- **CPU**: 2 cores
- **Disk**: 10GB for vector storage + logs

### Scaling Considerations

- **Qdrant**: Can scale horizontally with sharding
- **Bot instances**: Can run multiple replicas with shared Redis cache
- **MySQL**: Use read replicas for high read workloads

## 🔒 Security

InsightMesh follows the **8th Light Host Hardening Policy** for all infrastructure, aligned with SOC2 Security and Confidentiality criteria.

### Security Documentation

- 📘 **[Host Hardening Policy](docs/HOST_HARDENING_POLICY.md)** - Baseline security standards for VMs and containers covering:
  - Operating system hardening
  - Container runtime security
  - Secrets management
  - Identity and access management
  - Logging and monitoring
  - Patch management

### Key Security Features

- ✅ **Non-Root Containers**: All services run as non-root user (UID 1000)
- ✅ **Automated Security Scanning**: Bandit security linter in pre-commit hooks
- ✅ **Secrets Management**: AWS Secrets Manager integration, no plaintext secrets
- ✅ **Vulnerability Monitoring**: Regular dependency updates and CVE tracking
- ✅ **Encrypted Communications**: TLS 1.2+ for all external endpoints
- ✅ **Resource Limits**: CPU and memory limits prevent resource exhaustion
- ✅ **Audit Logging**: Centralized logs with Loki for security auditing

### Security Commands

```bash
# Run security scan
make security

# Full quality check (includes security)
make quality

# Scan Docker images for vulnerabilities
trivy image insightmesh-bot:latest
```

### Production Security Checklist

Before deploying to production:

- [ ] Change all default passwords in `.env` (use `openssl rand -base64 32`)
- [ ] Migrate secrets to AWS Secrets Manager or Vault
- [ ] Enable automatic security updates on host OS
- [ ] Disable SSH root login and password authentication
- [ ] Implement TLS certificates from trusted CA (Let's Encrypt)
- [ ] Set up centralized logging and alerting
- [ ] Configure backup and disaster recovery procedures
- [ ] Review [Host Hardening Policy](docs/HOST_HARDENING_POLICY.md) compliance

## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following code quality standards
4. Run quality checks: `make quality`
5. Commit your changes
6. Push to your branch
7. Open a Pull Request

See `CLAUDE.md` for detailed development workflow and standards.

---

**Questions?** Open an issue or check the documentation in the `/docs` directory.

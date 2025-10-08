# InsightMesh Slack AI Bot

A production-ready Slack bot with **RAG (Retrieval-Augmented Generation)** capabilities that provides intelligent, context-aware assistance using your own knowledge base.

## ✨ Features

### 🧠 **Advanced RAG Intelligence**
- **Pinecone Vector Search**: Semantic document search using dense embeddings
- **Adaptive Query Rewriting**: Automatically rewrites user queries for improved retrieval accuracy
- **Entity Boosting**: Intelligently boosts document relevance based on detected entities
- **Smart Diversification**: Returns chunks from multiple documents for comprehensive context
- **Direct LLM Integration**: OpenAI GPT models (gpt-4o-mini, gpt-4, etc.)
- **Knowledge-Aware Responses**: Uses your ingested documentation and data
- **Source Attribution**: Shows which documents informed each response

### 🔧 **Production Ready**
- **Thread Management**: Automatically manages conversation threads and context
- **Typing Indicators**: Shows typing states while generating responses
- **Online Presence**: Shows as "online" with a green status indicator
- **Custom User Prompts**: Users can customize bot behavior with `@prompt` commands
- **Health Dashboard**: Real-time monitoring UI at `http://localhost:8080/ui`
- **LLM Observability**: Langfuse integration for tracing, analytics, and cost monitoring
- **Prometheus Metrics**: Native metrics collection for infrastructure monitoring
- **Comprehensive Testing**: 245 tests with 72% code coverage
- **Service Container**: Protocol-based dependency injection architecture
- **Job Registry**: Scheduled tasks and background job management
- **Metric.ai Integration**: Direct API integration for metrics and analytics

### 🚀 **Easy Setup & Monitoring**
- **No Proxy Required**: Direct API integration eliminates infrastructure complexity
- **Simple Configuration**: Pinecone-only vector storage for streamlined setup
- **Document Ingestion**: CLI tool for loading from Google Drive
- **Health Monitoring**: Beautiful dashboard with real-time service status
- **Docker Deployment**: Full production deployment with comprehensive monitoring

## 🚀 Quick Start

**Requirements:** Python 3.11+

### 1. **Clone and Configure**
```bash
git clone https://github.com/8thlight/ai-slack-bot.git
cd ai-slack-bot

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

# Pinecone Vector Database (get from https://app.pinecone.io)
VECTOR_API_KEY=your-pinecone-api-key
VECTOR_ENVIRONMENT=us-east-1-aws
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base

# Database for user prompts and tasks
DATABASE_URL=mysql+pymysql://insightmesh_bot:insightmesh_bot_password@localhost:3306/bot

# Optional: Enable adaptive query rewriting (recommended)
RAG_ENABLE_QUERY_REWRITING=true
RAG_QUERY_REWRITE_MODEL=gpt-4o-mini
```

### 3. **Start Required Services**
```bash
# Start MySQL database
docker compose -f docker-compose.mysql.yml up -d

# Optional: Start Redis for caching
docker run -d -p 6379:6379 redis:alpine
```

### 4. **Install and Run**
```bash
# Install dependencies
make install

# Run the bot
make run
```

### 5. **Load Your Knowledge Base**
```bash
# Ingest documentation from Google Drive
cd ingest && python main.py --folder-id "YOUR_GOOGLE_DRIVE_FOLDER_ID"

# With custom metadata
cd ingest && python main.py --folder-id "YOUR_FOLDER_ID" --metadata '{"department": "engineering"}'
```

That's it! Your RAG-enabled Slack bot is now running with your custom knowledge base. 🎉

## 🔧 Pinecone Setup

### Create Your Pinecone Index

```python
import pinecone

pc = pinecone.Pinecone(api_key="your-pinecone-api-key")

pc.create_index(
    name="insightmesh-knowledge-base",
    dimension=1536,  # for text-embedding-3-small
    metric="cosine",
    spec=pinecone.ServerlessSpec(
        cloud="aws",
        region="us-east-1"
    )
)
```

### Pinecone Configuration

```bash
# Required settings
VECTOR_API_KEY=your-pinecone-api-key
VECTOR_ENVIRONMENT=us-east-1-aws  # or your Pinecone environment
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base

# Embedding model (matches index dimension)
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small  # 1536 dimensions
```

## Development Commands

### Setup and Installation
```bash
make install      # Install Python dependencies
make setup-dev    # Install dev tools + pre-commit hooks
```

### Running the Application
```bash
make run          # Run the Slack bot (requires .env file)
```

### Testing and Code Quality
```bash
make test         # Run test suite with pytest (245 tests)
make lint         # Auto-fix linting, formatting, and import issues
make lint-check   # Check code quality without fixing (used by pre-commit)
make quality      # Run complete pipeline: linting + type checking + tests
make test-coverage # Tests with coverage report (requires >70%, currently ~72%)
```

### Pre-commit and CI
```bash
make pre-commit   # Run all pre-commit hooks
make ci           # Run complete CI pipeline locally
```

### Docker
```bash
make docker-build # Build Docker image
make docker-run   # Run Docker container with .env
```

### Document Ingestion
```bash
# Ingest documents from Google Drive (THE ONLY SUPPORTED METHOD)
cd ingest && python main.py --folder-id "1ABC123DEF456GHI789"
cd ingest && python main.py --folder-id "1ABC123DEF456GHI789" --metadata '{"department": "engineering"}'

# First-time setup requires Google OAuth2 credentials
# See ingest/README.md for detailed setup instructions
```

## Slack App Setup Guide

This guide helps you configure your Slack app to work with the InsightMesh bot.

### Step 1: Create or Update App Configuration in Slack

1. Go to the Slack API Apps page (`https://api.slack.com/apps`) and select your bot application (or create a new one)
2. Provide a description (e.g., "InsightMesh Assistant helps you interact with your data using RAG and run agent processes")
3. Upload an app icon if desired
4. Click "Save Changes"

### Step 2: Configure OAuth Scopes

1. Navigate to "OAuth & Permissions" in the left navigation panel
2. Under "Scopes" > "Bot Token Scopes", add the following:
   - `app_mentions:read` - Read mentions of your app
   - `chat:write` - Send messages
   - `im:history` - View messages in direct messages
   - `im:read` - View basic information about direct messages
   - `im:write` - Send messages in direct messages
   - `mpim:history` - View messages in group direct messages
   - `groups:history` - View messages in private channels
   - `channels:history` - View messages in public channels
   - `chat:write.customize` - Customize messages (for blocks)
   - `chat:write.public` - Send messages to channels the app isn't in
   - `commands` - Add slash commands
   - `users:read` - View users in the workspace
   - `users:write` - Set bot's online presence status
   - `channels:read` - View basic info about public channels
   - `reactions:write` - Add reactions to messages
   - `files:write` - Upload, edit, and delete files
3. Click "Save Changes"

### Step 3: Enable Socket Mode (for development)

1. Navigate to "Socket Mode" in the left navigation panel
2. Toggle on "Enable Socket Mode"
3. Create an app-level token if prompted:
   - Name your token (e.g., "InsightMesh Socket Token")
   - Ensure the `connections:write` scope is added
   - Click "Generate"
   - Save the token (starts with `xapp-`) for use in environment variables

### Step 4: Configure Event Subscriptions

1. Navigate to "Event Subscriptions" in the left navigation panel
2. Toggle on "Enable Events"
3. Under "Subscribe to bot events" add the following:
   - `app_mention` - When the app is mentioned in a channel
   - `message.im` - When a message is sent in a DM with the app
   - `message.mpim` - When a message is sent in a group DM
   - `message.groups` - When a message is sent in a private channel
   - `message.channels` - When a message is sent in a public channel
4. Click "Save Changes"
5. IMPORTANT: After adding these events, you MUST reinstall your app for the changes to take effect

### Step 5: Disable App Home

1. Navigate to "App Home" in the left navigation panel
2. Toggle OFF "Home Tab"
3. Toggle ON "Allow users to send messages in app home"
4. Click "Save Changes"

### Step 6: Configure Interactivity

1. Navigate to "Interactivity & Shortcuts" in the left navigation panel
2. Toggle on "Interactivity"
3. You can leave the Request URL blank for Socket Mode
4. Click "Save Changes"

### Step 7: Reinstall App

1. Navigate to "Install App" in the left navigation panel
2. Click "Reinstall to Workspace" (required after adding new scopes)
3. Review permissions and click "Allow"
4. Note the new Bot User OAuth Token (starts with `xoxb-`) for use in environment variables

### Step 8: Configure Agent Processes

The bot supports running agent processes in response to user requests. These processes are defined in the `AGENT_PROCESSES` dictionary in `bot/handlers/agent_processes.py`.

By default, the following agent processes are available:

1. Data Indexing Job - Indexes documents into the RAG system
2. Slack Import Job - Imports data from Slack channels
3. Job Status Check - Checks status of running jobs

To add or modify agent processes:

1. Edit the `AGENT_PROCESSES` dictionary in `bot/handlers/agent_processes.py`
2. Make sure commands have the correct paths to their scripts
3. Ensure the scripts are available and executable in the expected locations

## Docker Deployment

Build and run the Docker container using Make targets:

```bash
make docker-build
make docker-run
```

## Architecture

### Technology Stack

- **slack-bolt**: Slack's official Python framework for building Slack apps
- **aiohttp**: Asynchronous HTTP client/server for Python
- **pydantic**: Data validation and settings management
- **OpenAI**: Primary LLM provider (GPT models)
- **Pinecone**: Vector database for semantic document search
- **RAG Pipeline**: Retrieval-Augmented Generation for knowledge-aware responses
- **MySQL**: Database for user prompts, tasks, and metrics
- **Redis**: Conversation caching
- **Langfuse**: LLM observability and prompt management

### Project Structure

```
bot/
├── config/            # Configuration management
│   └── settings.py    # Pydantic settings models for LLM, vector DB, and RAG
├── handlers/          # Event handling
│   ├── agent_processes.py  # Agent process functionality
│   ├── event_handlers.py   # Slack event handlers
│   └── message_handlers.py # Message handling logic
├── services/          # Core services
│   ├── protocols/          # Service protocol definitions
│   ├── vector_stores/      # Vector database implementations
│   ├── chunking/           # Document chunking services
│   ├── retrieval/          # Retrieval implementations
│   ├── llm_service.py      # RAG-enabled LLM service
│   ├── rag_service.py      # RAG orchestration and retrieval
│   ├── query_rewriter.py   # Adaptive query rewriting
│   ├── retrieval_service.py # Retrieval coordination
│   ├── vector_service.py   # Vector database abstraction
│   ├── embedding_service.py # Text embedding generation
│   ├── llm_providers.py    # LLM provider implementations
│   ├── slack_service.py    # Slack API integration
│   ├── factory.py          # Service factory with DI
│   ├── container.py        # Service container
│   └── formatting.py       # Message formatting utilities
├── models/            # Data models
│   ├── retrieval.py        # RAG models
│   ├── metric_record.py    # Metric.ai integration
│   └── slack_events.py     # Slack event models
├── migrations/        # Database migrations
├── tests/             # Comprehensive test suite (245 tests, 72% coverage)
├── utils/             # Utilities
│   ├── errors.py           # Error handling
│   └── logging.py          # Logging configuration
├── app.py             # Main application entry point
└── health.py          # Health check endpoints

ingest/                # Document ingestion services
├── main.py            # CLI entry point for Google Drive ingestion
├── services/          # Modular ingestion services
└── auth/              # Google OAuth2 authentication

tasks/                 # Background task scheduler
scripts/               # Utility scripts
evals/                 # LLM evaluation framework
```

### Core Architecture Patterns

#### Service Container & Dependency Injection
- Protocol-based service definitions in `services/protocols/`
- Centralized dependency injection via `ServiceContainer`
- Factory pattern for service creation with proper lifecycle management
- All services implement `BaseService` with `initialize()` and `close()` methods

#### RAG Pipeline
1. **Document Ingestion**: Google Drive → chunking → embedding → Pinecone storage
2. **Query Processing**: User question → adaptive query rewriting → embedding
3. **Retrieval**: Similarity search in Pinecone with entity boosting
4. **Diversification**: Smart selection from multiple documents
5. **Augmentation**: Retrieved context added to LLM prompt
6. **Generation**: LLM generates response with enhanced context
7. **Citation**: Source documents included in response

#### Adaptive Query Rewriting
The bot automatically rewrites user queries to improve retrieval accuracy:
- **Intent Classification**: Determines query type (greeting, fact, comparison, etc.)
- **Context Integration**: Uses conversation history for follow-up questions
- **Entity Extraction**: Identifies key entities for metadata filtering
- **Query Expansion**: Adds relevant terms for better semantic matching

#### Testing & Quality
- **245 tests** with **72% coverage**
- Unified quality tooling: Ruff (linting/formatting) + Pyright (type checking) + Bandit (security)
- Pre-commit hooks ensure code quality
- CI pipeline runs same checks as local development
- Test-driven development workflow

## Slack Integration Features

The bot implements several key Slack integration features:

### 1. Thread-Based Conversations
The bot automatically creates and maintains threads for all conversations, keeping discussions organized.

### 2. Typing Indicators
Shows when the bot is "thinking" while generating a response.

### 3. Universal Thread Response
The bot will respond to any message in a thread it's part of, without requiring explicit mentions.

### 4. Channel and Thread Support
The bot works in all types of Slack conversations with the following behavior:

- **Direct Messages (DMs)**: Always responds to all messages
- **Group Direct Messages**: Requires the `mpim:history` permission
- **Private Channels**: Requires the `groups:history` permission
- **Public Channels**: Requires the `channels:history` permission

In all non-DM contexts (channels, group DMs), the bot:
- Will respond to any message that directly @mentions it
- Will automatically respond to all subsequent messages in a thread once it has been mentioned in that thread
- No need to @mention the bot again for follow-up messages in the same thread

If the bot doesn't respond in threads where it was previously mentioned, check that you have all the required permission scopes configured in your Slack app settings.

### 5. Online Status
The bot maintains an online presence with a green status indicator.

## Agent Processes

The bot enables users to start and manage data processing jobs directly from Slack:

### Available Processes:

- **Data Indexing Job**: Index documents into the RAG system
- **Slack Import Job**: Import data from Slack channels
- **Check Job Status**: Check the status of running jobs

To start an agent process, users can type the command in chat:
```
Start a data indexing job
```

### Adding Custom Agent Processes

To add a new agent process:

1. Add it to the `AGENT_PROCESSES` dictionary in `bot/handlers/agent_processes.py`:
   ```python
   "agent_your_process": {
       "name": "Your Process Name",
       "description": "What your process does",
       "command": "python path/to/script.py arg1 arg2"
   }
   ```
2. Ensure the LLM system message (in `bot/handlers/message_handlers.py`) mentions the capability

## Testing Framework & Quality Standards

### Test Suite Requirements

**🎯 MANDATORY: All code changes MUST include comprehensive tests and pass 100% of the test suite.**

The project maintains a **245/245 test success rate (100%)** with **72% code coverage** - this standard must be preserved.

#### Test Commands
```bash
# Run all tests (REQUIRED before any commit)
make test                    # Full test suite (245 tests)
make test-coverage          # Tests with coverage report (requires >70%, currently ~72%)

# Quality checks (REQUIRED before commit)
make lint                   # Auto-fix with ruff + pyright + bandit
make lint-check            # Check-only mode (what CI uses)
make quality               # Run complete pipeline: linting + type checking + tests
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

### Code Quality Standards

#### Unified Quality Tooling (Auto-enforced)
- **Ruff**: Fast linting, formatting, and import sorting (replaces black + isort)
- **Pyright**: Type checking (strict mode, replaces MyPy)
- **Bandit**: Security vulnerability scanning

**🎯 Unified Makefile**: `make lint-check` ensures identical behavior across:
- Local development (`make lint`, `make lint-check`)
- Pre-commit hooks (automatic on git commit)
- CI pipeline (GitHub Actions)

**Benefits**: Single modern toolchain, faster execution, zero conflicts between tools.

## System Prompt Evaluation

Validate your system prompt behavior with comprehensive LLM-as-a-Judge evaluations:

```bash
cd evals
pip install -e .
python setup_langfuse_evals.py
```

This creates **12 test cases** and **10 evaluators** (5 custom + 5 managed) in Langfuse to test:
- **Professional Communication** - Executive-appropriate tone
- **Source Transparency** - Clear knowledge base vs general knowledge indication
- **RAG Behavior** - Knowledge retrieval integration
- **Executive Readiness** - Strategic decision support
- **Plus managed evaluators** - Helpfulness, conciseness, coherence, correctness, harmlessness

See [`evals/README.md`](evals/README.md) for complete evaluation setup and [`evals/evaluator_prompts.md`](evals/evaluator_prompts.md) for Langfuse configurations.

## 📊 Monitoring & Observability

### Health Dashboard (`http://localhost:8080/ui`)
- **🟢 Real-time status** of all services (LLM, cache, Langfuse, metrics)
- **📈 Big metrics display** showing memory usage, active conversations, system uptime
- **⚡ Smart error handling** with detailed troubleshooting information
- **🔄 Auto-refresh** every 10 seconds with manual refresh option
- **📱 Mobile-friendly** responsive design

### Prometheus Integration
- **Native metrics collection** for infrastructure monitoring
- **Standard /metrics endpoint** at `http://localhost:8080/api/prometheus`
- **Grafana-compatible** metrics for advanced dashboards
- **Active conversation tracking** and performance metrics

### LLM Observability with Langfuse
- **Cost tracking** per user, conversation, and model
- **Performance analytics** and prompt optimization insights
- **Conversation analytics** and user behavior patterns
- **Error tracking** with detailed LLM debugging information
- **Prompt management** - Store and version system prompts in Langfuse
- **Query rewriting traces** - See how queries are rewritten for better retrieval

See [`docs/LANGFUSE_SETUP.md`](docs/LANGFUSE_SETUP.md) for complete setup instructions.

## Troubleshooting

If you're experiencing issues:

1. **Slack Configuration**: Ensure all Slack app permissions and event subscriptions are configured correctly
2. **Environment Variables**: Verify all required variables in `.env` are set (Slack tokens, LLM API key, Pinecone credentials)
3. **LLM Provider**: Test your OpenAI API key is valid and has sufficient quota
4. **Pinecone**:
   - Check your index exists with `pc.list_indexes()`
   - Verify API key is correct
   - Ensure environment matches (e.g., `us-east-1-aws`)
   - Confirm index dimension (1536 for text-embedding-3-small)
5. **Document Ingestion**: Use `cd ingest && python main.py --folder-id YOUR_ID` to ingest from Google Drive
6. **Bot Logs**: Look for specific error messages in the application logs
7. **Query Rewriting**: Check Langfuse traces to see how queries are being rewritten
8. **Pre-commit Hooks**: If commit fails, run `make lint` to auto-fix issues, then commit again

## Notes About Socket Mode

While this implementation uses Socket Mode for development convenience, we recommend:

1. Using Socket Mode during development for easy testing
2. Switching to HTTP endpoints for production deployments by:
   - Disabling Socket Mode in your Slack app settings
   - Setting up a public HTTP endpoint for your bot
   - Updating your app to use that endpoint instead of Socket Mode

# InsightMesh Slack Bot - Core Service

The main Slack bot service that provides RAG-enabled AI assistance with comprehensive monitoring and health dashboards.

## Features

- **RAG-Enabled Responses**: Retrieval-Augmented Generation using your knowledge base
- **Multi-Provider LLM Support**: OpenAI, Anthropic, or local Ollama models
- **Vector Search**: Dense vector search with Pinecone or Elasticsearch
- **Thread Management**: Automatic conversation threading and context management
- **Health Monitoring**: Real-time dashboard at `http://localhost:8080/ui`
- **Prometheus Metrics**: Native metrics collection for monitoring
- **Langfuse Integration**: LLM observability and cost tracking

## Quick Start

```bash
# Install dependencies
make install

# Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Start required services
docker compose -f docker-compose.mysql.yml up -d

# Run the bot
make run
```

## Health Dashboard

Access the health dashboard at `http://localhost:8080/ui` to monitor:

- **Service Status**: LLM API, cache, Langfuse, and metrics services
- **System Metrics**: Memory usage, active conversations, uptime
- **Real-time Updates**: Auto-refresh every 10 seconds
- **Error Details**: Comprehensive troubleshooting information

## Configuration

Key environment variables:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# LLM Provider
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-api-key
LLM_MODEL=gpt-4o-mini

# RAG Configuration
VECTOR_ENABLED=true
VECTOR_PROVIDER=pinecone
VECTOR_API_KEY=your-pinecone-api-key

# Database
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/bot
```

## Architecture

```
bot/
├── app.py                 # Main application entry point
├── config/
│   └── settings.py        # Configuration management
├── handlers/              # Event and message handling
├── services/              # Core services (LLM, RAG, vector, etc.)
├── utils/                 # Utilities and helpers
├── health.py              # Health monitoring service
├── health_ui/             # React-based health dashboard
└── models/                # Database models
```

## Health Monitoring

The bot includes comprehensive health monitoring:

- **Health Endpoints**: `/api/health`, `/api/ready`, `/api/metrics`
- **React Dashboard**: Modern UI with real-time updates
- **Prometheus Integration**: Standard metrics endpoint
- **Service Checks**: LLM API, cache, database, and vector store status

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Start health dashboard development
cd health_ui && npm run dev
```

## Docker Deployment

```bash
# Build and run
make docker-build
make docker-run

# Or use docker-compose
docker compose up -d
```

## Monitoring & Observability

- **Health Dashboard**: Real-time service monitoring
- **Prometheus Metrics**: Infrastructure monitoring integration
- **Langfuse Integration**: LLM cost tracking and analytics
- **Structured Logging**: Comprehensive application logging

See the main project README for complete setup and configuration instructions.

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

## Testing Framework

Uses pytest with async support:
- Test files in `src/tests/`
- Coverage reporting available
- Run with `PYTHONPATH=src pytest -q src/tests`
# Insight Mesh Slack AI Bot

A production-ready Slack bot with **RAG (Retrieval-Augmented Generation)** capabilities that provides intelligent, context-aware assistance using your own knowledge base.

## ✨ Features

### 🧠 **RAG-Powered Intelligence**
- **Vector Database**: ChromaDB or Pinecone for semantic document search
- **Direct LLM Integration**: OpenAI, Anthropic, or local Ollama models
- **Knowledge-Aware**: Responds using your ingested documentation and data
- **Source Attribution**: Shows which documents informed the response

### 🔧 **Production Ready**
- **Thread Management**: Automatically manages conversation threads and context
- **Typing Indicators**: Shows typing states while generating responses
- **Online Presence**: Shows as "online" with a green status indicator
- **Custom User Prompts**: Users can customize bot behavior with `@prompt` commands
- **Comprehensive Testing**: 154 tests with 100% reliability
- **CI/CD Pipeline**: GitHub Actions with quality checks and Docker builds

### 🚀 **Easy Setup**
- **No Proxy Required**: Direct API integration eliminates infrastructure complexity
- **Flexible Configuration**: Support for multiple LLM and vector database providers
- **Document Ingestion**: CLI tool for loading your knowledge base
- **Docker Deployment**: Full production deployment with monitoring

## 🚀 Quick Start

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

# Pinecone (get from https://app.pinecone.io)
VECTOR_ENABLED=true
VECTOR_PROVIDER=pinecone
VECTOR_URL=https://your-index.svc.environment.pinecone.io
VECTOR_API_KEY=your-pinecone-api-key
VECTOR_COLLECTION_NAME=knowledge-base

# Optional: Database for user prompts (use SQLite if not provided)
DATABASE_URL=postgresql://user:pass@localhost:5432/slack_bot
```

### 3. **Install and Run**
```bash
# Install dependencies
make install

# Run the bot
make run
```

### 4. **Load Your Knowledge Base**
```bash
# Ingest documentation
cd src
python ingest_documents.py --directory ../docs/
python ingest_documents.py --url https://docs.yourcompany.com/api.md
python ingest_documents.py --status  # Check system status
```

That's it! Your RAG-enabled Slack bot is now running with your custom knowledge base. 🎉

## Slack App Setup Guide

This guide helps you configure your Slack app to work with the Insight Mesh bot.

### Step 1: Create or Update App Configuration in Slack

1. Go to the Slack API Apps page (`https://api.slack.com/apps`) and select your bot application (or create a new one)
2. Provide a description (e.g., "Insight Mesh Assistant helps you interact with your data using RAG and run agent processes")
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
   - `app_mentions:read` - Read @mentions
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
   - Name your token (e.g., "Insight Mesh Socket Token")
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
   - `message` - When a message is sent (general catch-all)
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

### Step 8: Set Environment Variables

Create a `.env` file in your project root with the following variables:

```bash
SLACK_BOT_TOKEN="xoxb-your-bot-token"
SLACK_APP_TOKEN="xapp-your-app-token"
SLACK_BOT_ID=""  # Optional, will be extracted from token if not provided
LLM_API_URL="http://your-llm-api-url"
LLM_API_KEY="your-llm-api-key"
LLM_MODEL="gpt-4o-mini"  # or other model supported by your LLM API
```

### Step 9: Configure Agent Processes

The bot supports running agent processes in response to user requests. These processes are defined in the `AGENT_PROCESSES` dictionary in `handlers/agent_processes.py`.

By default, the following agent processes are available:

1. Data Indexing Job - Indexes documents into the RAG system
2. Slack Import Job - Imports data from Slack channels
3. Job Status Check - Checks status of running jobs

To add or modify agent processes:

1. Edit the `AGENT_PROCESSES` dictionary in `handlers/agent_processes.py`
2. Make sure commands have the correct paths to their scripts
3. Ensure the scripts are available and executable in the expected locations

## Docker Deployment

Build and run the Docker container using Make targets:

```bash
make docker-build
make docker-run
```

## Architecture

The bot is built using:
- **slack-bolt**: Slack's official Python framework for building Slack apps
- **aiohttp**: Asynchronous HTTP client/server for Python
- **pydantic**: Data validation and settings management
- **Direct LLM Integration**: OpenAI, Anthropic, or local Ollama models
- **Vector Databases**: ChromaDB or Pinecone for semantic document search
- **RAG Pipeline**: Retrieval-Augmented Generation for knowledge-aware responses

### Project Structure

```
slack-bot/
├── config/            # Configuration management
│   ├── settings.py    # Pydantic settings models for LLM, vector DB, and RAG
├── handlers/          # Event handling
│   ├── agent_processes.py  # Agent process functionality
│   ├── event_handlers.py   # Slack event handlers
│   ├── message_handlers.py # Message handling logic
├── services/          # Core services
│   ├── llm_service.py      # RAG-enabled LLM service
│   ├── rag_service.py      # RAG orchestration and retrieval
│   ├── vector_service.py   # Vector database abstraction (ChromaDB/Pinecone)
│   ├── embedding_service.py # Text embedding generation
│   ├── llm_providers.py    # Direct LLM provider implementations
│   ├── slack_service.py    # Slack API integration
│   ├── formatting.py       # Message formatting utilities
├── utils/             # Utilities
│   ├── errors.py           # Error handling
│   ├── logging.py          # Logging configuration
├── ingest_documents.py     # CLI tool for document ingestion
├── app.py             # Main application entry point
├── Dockerfile         # Docker configuration
└── requirements.txt   # Python dependencies
```

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

1. Add it to the `AGENT_PROCESSES` dictionary in `handlers/agent_processes.py`:
   ```python
   "agent_your_process": {
       "name": "Your Process Name",
       "description": "What your process does",
       "command": "python path/to/script.py arg1 arg2"
   }
   ```
2. Ensure the LLM system message (in `handlers/message_handlers.py`) mentions the capability

## Development

### Local Setup

1. (Optional) Create and activate a virtual environment
2. Install dependencies and run via Make:
   ```bash
   make install
   make run
   ```

### Code Organization

- **config/settings.py**: Comprehensive settings for LLM providers, vector databases, and RAG configuration
- **handlers/**: Event and message handling with RAG integration
- **services/**: RAG pipeline, vector storage, embedding generation, and direct LLM providers
- **utils/**: Utility functions and helpers
- **ingest_documents.py**: CLI tool for loading your knowledge base
- **app.py**: Main application entry point

## Troubleshooting

If you're experiencing issues:

1. **Slack Configuration**: Ensure all Slack app permissions and event subscriptions are configured correctly
2. **Environment Variables**: Verify all required variables in `.env` are set (Slack tokens, LLM API key, vector DB credentials)
3. **LLM Provider**: Test your OpenAI/Anthropic API key is valid and has sufficient quota
4. **Vector Database**: 
   - **Pinecone**: Check your index exists and API key is correct
   - **ChromaDB**: Ensure the directory is writable
5. **Document Ingestion**: Use `python ingest_documents.py --status` to check your knowledge base
6. **Bot Logs**: Look for specific error messages in the application logs
7. **RAG Pipeline**: Test with `VECTOR_ENABLED=false` to isolate LLM vs vector DB issues

## Notes About Socket Mode

While this implementation uses Socket Mode for development convenience, we recommend:

1. Using Socket Mode during development for easy testing
2. Switching to HTTP endpoints for production deployments by:
   - Disabling Socket Mode in your Slack app settings
   - Setting up a public HTTP endpoint for your bot
   - Updating your app to use that endpoint instead of Socket Mode

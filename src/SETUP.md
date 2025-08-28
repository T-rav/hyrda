# Slack Bot Setup Guide

This guide will help you configure your Slack app to work with the Insight Mesh bot.

## Step 1: Create or Update App Configuration in Slack

1. Go to [Slack API Apps page](https://api.slack.com/apps) and select your bot application (or create a new one)
2. Provide a description (e.g., "Insight Mesh Assistant helps you interact with your data using RAG and run agent processes")
3. Upload an app icon if desired
4. Click "Save Changes"

## Step 2: Configure OAuth Scopes

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

## Step 3: Enable Socket Mode (for development)

1. Navigate to "Socket Mode" in the left navigation panel
2. Toggle on "Enable Socket Mode"
3. Create an app-level token if prompted:
   - Name your token (e.g., "Insight Mesh Socket Token")
   - Ensure the `connections:write` scope is added
   - Click "Generate"
   - Save the token (starts with `xapp-`) for use in environment variables

## Step 4: Configure Event Subscriptions

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
5. **IMPORTANT**: After adding these events, you MUST reinstall your app for the changes to take effect

## Step 5: Disable App Home

1. Navigate to "App Home" in the left navigation panel
2. Toggle OFF "Home Tab" 
3. Toggle ON "Allow users to send messages in app home"
4. Click "Save Changes"

## Step 6: Configure Interactivity

1. Navigate to "Interactivity & Shortcuts" in the left navigation panel
2. Toggle on "Interactivity"
3. You can leave the Request URL blank for Socket Mode
4. Click "Save Changes"

## Step 7: Reinstall App

1. Navigate to "Install App" in the left navigation panel
2. Click "Reinstall to Workspace" (required after adding new scopes)
3. Review permissions and click "Allow"
4. Note the new Bot User OAuth Token (starts with `xoxb-`) for use in environment variables

## Step 8: Set Environment Variables

Create a `.env` file in your project root with the following variables:

```bash
SLACK_BOT_TOKEN="xoxb-your-bot-token"
SLACK_APP_TOKEN="xapp-your-app-token"
SLACK_BOT_ID=""  # Optional, will be extracted from token if not provided
LLM_API_URL="http://your-llm-api-url"
LLM_API_KEY="your-llm-api-key"
LLM_MODEL="gpt-4o-mini"  # or other model supported by your LLM API
```

## Step 9: Configure Agent Processes

The bot supports running agent processes in response to user requests. These processes are defined in the `AGENT_PROCESSES` dictionary in `handlers/agent_processes.py`.

By default, the following agent processes are available:

1. **Data Indexing Job** - Indexes documents into the RAG system
2. **Slack Import Job** - Imports data from Slack channels
3. **Job Status Check** - Checks status of running jobs

To add or modify agent processes:

1. Edit the `AGENT_PROCESSES` dictionary in `handlers/agent_processes.py`
2. Make sure commands have the correct paths to their scripts
3. Ensure the scripts are available and executable in the expected locations

## Step 10: Run the Bot

### Running Locally

```bash
cd slack-bot
python app.py
```

### Running with Docker

```bash
cd slack-bot
docker build -t insight-mesh-slack-bot .
docker run -d --env-file .env --name insight-mesh-bot insight-mesh-slack-bot
```

### Running with Docker Compose

```bash
# From the project root
docker-compose up -d slack-bot
```

## Configuration Options

The bot uses Pydantic for configuration management. The main settings are defined in `config/settings.py`:

- **SlackSettings**: Manages Slack tokens and credentials
- **LLMSettings**: Manages LLM API connection details
- **AgentSettings**: Manages agent process configuration
- **Settings**: Main application settings

You can customize these settings via environment variables.

## Verifying Setup

1. In Slack, you should see your bot in the sidebar with an online status (green dot)
2. Try sending a direct message to the bot
3. Try mentioning the bot in a channel with `@insight-mesh hello`
4. The bot should respond with messages in a thread
5. Try starting an agent process by typing "Start a data indexing job"
6. The bot should respond with a confirmation that the process has started 
#!/bin/bash

# Check if .env file exists in parent directory
if [ ! -f ../.env ]; then
    echo "Error: .env file not found in project root. Please create it with the required environment variables."
    echo "Required variables: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LLM_API_URL, LLM_API_KEY"
    exit 1
fi

# Load environment variables from parent .env file
export $(grep -v '^#' ../.env | xargs)

# Check for required environment variables
if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_APP_TOKEN" ]; then
    echo "Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN environment variables are required."
    exit 1
fi

# Extract Bot ID from token
if [[ $SLACK_BOT_TOKEN =~ ^xoxb-([^-]+) ]]; then
    export SLACK_BOT_ID=${BASH_REMATCH[1]}
    echo "Extracted Bot ID: $SLACK_BOT_ID"
else
    echo "Warning: Could not extract Bot ID from token."
fi

echo "Starting Insight Mesh Slack AI Bot..."
echo "Press Ctrl+C to stop the bot."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Install dependencies if needed
pip install -r requirements.txt

# Run the bot
python app.py 
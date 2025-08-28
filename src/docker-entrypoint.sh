#!/bin/bash
set -e

# Extract Bot ID from token if not provided
if [ -z "$SLACK_BOT_ID" ] && [[ "$SLACK_BOT_TOKEN" =~ ^xoxb-([^-]+) ]]; then
    export SLACK_BOT_ID=${BASH_REMATCH[1]}
    echo "Extracted Bot ID: $SLACK_BOT_ID"
else
    echo "Using provided Bot ID or could not extract from token."
fi

# Check for required environment variables
if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_APP_TOKEN" ]; then
    echo "Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN environment variables are required."
    exit 1
fi

# Execute the command (default is to run the app)
exec "$@" 
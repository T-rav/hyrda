#!/bin/bash

# Navigate to the src directory
cd /Users/travisfrisinger/Documents/projects/ai-slack-bot/src

# Activate virtual environment
source ../venv/bin/activate

# Set environment variables to disable optional services and use correct API key
export DATABASE_ENABLED=false
export VECTOR_ENABLED=false
export CACHE_ENABLED=false
export LLM_API_KEY="$(grep OPENAI_API_KEY .env | cut -d'=' -f2)"

echo "Starting Slack bot with simplified configuration..."
echo "LLM API Key configured: ${LLM_API_KEY:0:20}..."

# Start the bot
python app.py

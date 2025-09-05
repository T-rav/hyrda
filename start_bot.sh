#!/bin/bash

# Navigate to the bot directory
cd /Users/travisfrisinger/Documents/projects/ai-slack-bot/bot

# Activate virtual environment
source venv/bin/activate

echo "Starting Slack bot with RAG enabled..."

# Start the bot
python app.py

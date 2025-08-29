#!/bin/bash

# Navigate to the src directory
cd /Users/travisfrisinger/Documents/projects/ai-slack-bot/src

# Activate virtual environment
source ../venv/bin/activate

echo "Starting Slack bot with Pinecone RAG enabled..."

# Start the bot
python app.py

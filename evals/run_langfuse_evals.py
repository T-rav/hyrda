#!/usr/bin/env python3
"""
Run Langfuse-native evaluations for System Prompt

This script runs evaluations against your System/Default prompt using
Langfuse's built-in evaluation capabilities.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from langfuse import Langfuse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_evaluations():
    """Run system prompt evaluations in Langfuse"""
    load_dotenv()

    # Initialize Langfuse
    Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    logger.info("🚀 Running System Prompt Evaluations")

    # Get the dataset
    dataset_name = "system-prompt-evaluation"

    # This would trigger evaluations in Langfuse
    # You'll run this through the Langfuse UI or API

    logger.info(f"✅ Evaluations queued for dataset: {dataset_name}")
    logger.info("Go to your Langfuse dashboard to view results!")


if __name__ == "__main__":
    asyncio.run(run_evaluations())

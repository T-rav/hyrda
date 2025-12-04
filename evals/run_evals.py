#!/usr/bin/env python3
"""
Simple evaluation runner for system prompt testing

Usage:
    python evals/run_evals.py
    python evals/run_evals.py --quick    # Run subset of tests
    python evals/run_evals.py --judge-model gpt-4o    # Use specific judge model
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add bot directory to path for imports
bot_dir = Path(__file__).parent.parent / "bot"
sys.path.insert(0, str(bot_dir))

from dotenv import load_dotenv


async def main():
    """Run evaluations with command line interface"""
    parser = argparse.ArgumentParser(description="Run system prompt evaluations")
    parser.add_argument(
        "--quick", action="store_true", help="Run quick evaluation (subset of tests)"
    )
    parser.add_argument(
        "--judge-model",
        default="gpt-4o",
        help="Model to use for judging (default: gpt-4o)",
    )
    parser.add_argument(
        "--output", default="eval_results.json", help="Output file for results"
    )
    parser.add_argument("--langfuse-project", help="Langfuse project name (optional)")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Validate required environment variables
    required_vars = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set the following in your .env file:")
        for var in missing_vars:
            print(f"  {var}=your_key_here")
        return 1

    # Import after environment is validated
    from langfuse import Langfuse
    from openai import AsyncOpenAI

    from prompt_evaluator import SystemPromptEvaluator

    print("🚀 Starting System Prompt Evaluation")
    print("=" * 50)

    # Initialize clients
    langfuse_kwargs = {
        "public_key": os.getenv("LANGFUSE_PUBLIC_KEY"),
        "secret_key": os.getenv("LANGFUSE_SECRET_KEY"),
        "host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    }

    if args.langfuse_project:
        langfuse_kwargs["project"] = args.langfuse_project

    try:
        langfuse = Langfuse(**langfuse_kwargs)
        openai_client = AsyncOpenAI(api_key=os.getenv("LLM_API_KEY"))

        # Create evaluator
        evaluator = SystemPromptEvaluator(langfuse, openai_client, args.judge_model)

        # Run evaluation suite
        suite = await evaluator.run_eval_suite()

        # Determine success
        success = suite.avg_score >= 0.7 and suite.failed_tests == 0

        if success:
            print("\n🎉 All evaluations PASSED!")
            print(
                f"Your system prompt is working great! (Average score: {suite.avg_score:.3f})"
            )
        else:
            print(
                f"\n⚠️  Some evaluations FAILED (Pass rate: {suite.passed_tests}/{suite.total_tests})"
            )
            print("Consider updating your System/Default prompt template in Langfuse")

        print(f"\n📊 Results saved to: {args.output}")
        return 0 if success else 1

    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

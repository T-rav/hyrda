#!/usr/bin/env python3
"""
Debug the threshold values being used
"""

import asyncio
import sys
import os

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from config.settings import Settings

async def debug_thresholds():
    """Debug threshold values"""

    # Load environment
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.split('#')[0].strip()
                    os.environ.setdefault(key.strip(), value)

    settings = Settings()

    print("🔍 Current Threshold Settings:")
    print("=" * 40)
    print(f"RAG_SIMILARITY_THRESHOLD: {settings.rag.similarity_threshold}")
    print(f"RAG_RESULTS_SIMILARITY_THRESHOLD: {settings.rag.results_similarity_threshold}")
    print()
    print(f"Calculated initial threshold: {max(0.1, settings.rag.similarity_threshold - 0.2)}")
    print(f"Final results threshold: {settings.rag.results_similarity_threshold}")
    print()

    print("🎯 Apple document scores without boosting:")
    print("- Apple Project Details File: ~0.475")
    print("- Other Apple docs: ~0.43-0.45")
    print()

    print("✅ With +0.25 entity boost:")
    print("- Apple Project Details File: ~0.725")
    print("- Other Apple docs: ~0.68-0.70")
    print()

    initial_threshold = max(0.1, settings.rag.similarity_threshold - 0.2)
    results_threshold = settings.rag.results_similarity_threshold

    print("🔬 Analysis:")
    if 0.475 >= initial_threshold:
        print(f"✅ Apple docs (0.475) pass initial threshold ({initial_threshold})")
    else:
        print(f"❌ Apple docs (0.475) fail initial threshold ({initial_threshold})")

    if 0.725 >= results_threshold:
        print(f"✅ Boosted Apple docs (0.725) pass results threshold ({results_threshold})")
    else:
        print(f"❌ Boosted Apple docs (0.725) fail results threshold ({results_threshold})")

if __name__ == "__main__":
    asyncio.run(debug_thresholds())

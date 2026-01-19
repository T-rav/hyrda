"""Test supervisor subgraph directly."""

import asyncio
import logging
import sys
from pathlib import Path

# Add custom_agents to path
sys.path.insert(0, str(Path(__file__).parent / "custom_agents"))

# Setup logging to see all debug output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

async def test_supervisor():
    """Test the supervisor subgraph with a simple research brief."""
    from profiler.nodes.graph_builder import build_supervisor_subgraph

    # Build the supervisor subgraph
    supervisor_graph = build_supervisor_subgraph()

    # Print graph structure
    print("\n===== GRAPH STRUCTURE =====")
    print(f"Nodes: {list(supervisor_graph.nodes.keys())}")
    print()

    # Create a simple test research brief
    test_brief = """
## Company Overview
What is Costco's business model?
Who are their main customers?

## Financial Performance
What is their revenue trend?
What are their profit margins?
"""

    # Stream the subgraph to see all steps
    result = None
    async for event in supervisor_graph.astream({
        "research_brief": test_brief,
        "profile_type": "company",
        "focus_area": "",
    }):
        print(f"\nEvent: {event}")
        if "__end__" in event:
            result = event["__end__"]

    print("\n===== RESULT =====")
    if result:
        print(f"Notes: {len(result.get('notes', []))} items")
        print(f"Raw notes: {len(result.get('raw_notes', []))} items")
        print(f"All question groups: {len(result.get('all_question_groups', []))} groups")
        print(f"Completed groups: {len(result.get('completed_groups', []))} groups")

        if result.get('notes'):
            print("\nFirst note:")
            print(result['notes'][0][:200] + "...")
    else:
        print("No result (graph did not reach __end__)")

    return result

if __name__ == "__main__":
    asyncio.run(test_supervisor())

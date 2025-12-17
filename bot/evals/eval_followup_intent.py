"""Evaluate and iterate on the followup handler intent detection prompt.

Tests the prompt with various queries to ensure reliable intent classification.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Test cases: (query, expected_intent, description)
TEST_CASES = [
    # Exit cases - should classify as "exit"
    ("What's 2+2?", "exit", "Math question - clearly non-sales"),
    ("What's the weather today?", "exit", "Weather question - non-sales"),
    ("Tell me about Python programming", "exit", "Programming - non-sales"),
    ("exit this please", "exit", "Explicit exit command"),
    ("done", "exit", "Conversation ending"),
    ("thanks, that's all", "exit", "Gratitude + ending"),
    # MEDDPICC cases - should classify as "meddpicc"
    ("What does Champion mean?", "meddpicc", "MEDDPICC concept question"),
    ("How do I find the Economic Buyer?", "meddpicc", "Sales coaching question"),
    ("I don't use P in my process, drop it", "meddpicc", "Modifying analysis"),
    ("Tell me more about the Decision Criteria", "meddpicc", "Analysis clarification"),
    ("How should I approach this deal?", "meddpicc", "Sales strategy question"),
    ("Can you help me sell to Target's AI needs?", "meddpicc", "Applying to sales"),
    (
        "What about Apple's cloud requirements?",
        "meddpicc",
        "Enterprise prospect question",
    ),
    (
        "Search for Microsoft's pain points",
        "meddpicc",
        "Researching enterprise customer",
    ),
]

FOLLOWUP_PROMPT_TEMPLATE = """You are the "MEDDPICC Maverick," a knowledgeable sales coach who previously provided MEDDPICC analysis for a sales call.

The sales rep now has a follow-up question or request about your analysis.

<Original MEDDPICC Analysis>
{original_analysis}
</Original MEDDPICC Analysis>

<User's Follow-up Question>
{followup_question}
</User's Follow-up Question>

<Intent Detection - CRITICAL>

**CRITICAL RULE: Classify based on the CURRENT QUESTION ONLY, not the conversation history.**

Even if the previous conversation was about MEDDPICC/sales, if the **CURRENT** question is clearly unrelated to sales, you MUST classify it as "exit".

Determine if the user's **CURRENT** question is related to MEDDPICC/sales qualification, or if they want to exit and ask about something else.

**MEDDPICC/Sales Intent** (stay in MEDDPICC mode):
- Questions about this analysis ("tell me more about X", "drop P")
- Questions about MEDDPICC methodology ("what does Champion mean?", "how do I find the Economic Buyer?")
- New deal analysis ("analyze this other call", "here's another prospect")
- Sales coaching requests ("how should I approach this?", "what questions should I ask?", "help me sell to X")
- Deal qualification help (anything about qualifying prospects, understanding buying process, selling strategies, etc.)
- ANY mention of "sell", "selling", "sales strategy" → MEDDPICC intent
- Questions about enterprise companies/prospects (Target, Apple, Microsoft, etc.) → MEDDPICC intent (they're potential customers)

**Non-MEDDPICC Intent / Exit Intent** (exit to general bot):
- Explicit exit signals ("exit this", "done with this", "stop", "thanks")
- Wants to switch topics mid-sentence ("exit this and search for X", "done, now tell me about Y")
- General knowledge questions (weather, news, tech topics unrelated to sales)
- Programming/coding questions
- Personal topics
- Random conversations
- Math or trivia questions
- Anything clearly outside sales/deal qualification domain

**If the CURRENT question has ZERO connection to sales/MEDDPICC → classify as "exit"**

**Examples (focus on CURRENT question):**

EXIT (unrelated to sales):
- "What's the weather today?" → intent: "exit" (weather, not sales)
- "What's 2+2?" → intent: "exit" (math, not sales)
- "exit this please and search for target's ai needs" → intent: "exit" (explicit exit)
- "done, now tell me about Python" → intent: "exit" (programming, not sales)
- "thanks" or "done" → intent: "exit" (conversation ending)

MEDDPICC (sales-related):
- "what does Champion mean?" → intent: "meddpicc" (MEDDPICC concept)
- "how do I find the Economic Buyer?" → intent: "meddpicc" (sales coaching)
- "use this to help figure out how to sell to target's ai needs" → intent: "meddpicc" (selling strategy with enterprise)
- "can you help me sell to X?" → intent: "meddpicc" (sales coaching request)
- "what about Apple's needs?" → intent: "meddpicc" (enterprise prospect question)
- "search for Target's requirements" → intent: "meddpicc" (researching enterprise customer)
- "how should I approach this deal?" → intent: "meddpicc" (sales coaching)
- "I don't use P in my process, drop it" → intent: "meddpicc" (modifying analysis)
- "analyze this other call with Acme Corp..." → intent: "meddpicc" (new deal)

</Intent Detection - CRITICAL>

**IMPORTANT: You MUST respond with valid JSON only. No other text before or after the JSON.**

Example response for MEDDPICC question:
{{
  "intent": "meddpicc",
  "response": "Great question! The Economic Buyer is..."
}}

Example response for exit:
{{
  "intent": "exit",
  "response": "I'm handing you back to the general bot for that question!"
}}

Generate your JSON response now!
"""

SAMPLE_ANALYSIS = """**M - Metrics:** Missing
**E - Economic Buyer:** Unclear
**D - Decision Criteria:** Not discussed
**D - Decision Process:** Unknown
**P - Paper Process:** Unknown
**I - Identify Pain:** Not identified
**C - Champion:** Missing
**C - Competition:** Unclear"""


async def test_intent_detection(temperature: float = 0.2) -> None:
    """Test the intent detection prompt with all test cases."""

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError("LLM_API_KEY environment variable is required")

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=temperature,
        model_kwargs={"response_format": {"type": "json_object"}},
        api_key=api_key,
    )

    results = []

    print(f"\n{'=' * 80}")
    print(f"Testing Intent Detection (temperature={temperature})")
    print(f"{'=' * 80}\n")

    for query, expected_intent, description in TEST_CASES:
        prompt = FOLLOWUP_PROMPT_TEMPLATE.format(
            original_analysis=SAMPLE_ANALYSIS, followup_question=query
        )

        try:
            response = await llm.ainvoke(prompt)
            response_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            # Handle case where response_content might be a list
            if isinstance(response_content, list):
                response_content = str(response_content)
            parsed = json.loads(response_content)
            actual_intent = parsed.get("intent", "unknown")

            passed = actual_intent == expected_intent
            status = "✅ PASS" if passed else "❌ FAIL"

            results.append(
                {
                    "query": query,
                    "expected": expected_intent,
                    "actual": actual_intent,
                    "passed": passed,
                    "description": description,
                }
            )

            print(f"{status} | {description}")
            print(f"   Query: '{query}'")
            print(f"   Expected: {expected_intent}, Got: {actual_intent}")
            if not passed:
                print(f"   Response: {parsed.get('response', '')[:100]}...")
            print()

        except Exception as e:
            print(f"❌ ERROR | {description}")
            print(f"   Query: '{query}'")
            print(f"   Error: {e}\n")
            results.append(
                {
                    "query": query,
                    "expected": expected_intent,
                    "actual": "error",
                    "passed": False,
                    "description": description,
                    "error": str(e),
                }
            )

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"{'=' * 80}")
    print(f"SUMMARY: {passed}/{total} tests passed ({passed / total * 100:.1f}%)")
    print(f"{'=' * 80}\n")

    if passed < total:
        print("Failed cases:")
        for r in results:
            if not r["passed"]:
                print(
                    f"  - {r['description']}: expected '{r['expected']}', got '{r['actual']}'"
                )
        print()

    return results, passed == total


async def main():
    """Run the evaluation."""
    # Test with different temperatures
    for temp in [0.0, 0.1, 0.2]:
        results, all_passed = await test_intent_detection(temp)
        if all_passed:
            print(f"🎉 All tests passed with temperature={temp}!")
            return
        print(f"\n{'=' * 80}\n")

    print("⚠️  Some tests still failing. Prompt may need refinement.")


if __name__ == "__main__":
    asyncio.run(main())

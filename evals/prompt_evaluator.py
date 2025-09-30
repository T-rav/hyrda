#!/usr/bin/env python3
"""
System Prompt Evaluation Framework

Tests core behaviors defined in the Insight Mesh system prompt using LLM-as-a-Judge.
Integrates with Langfuse for tracking and dataset management.

Run this to validate that your system prompt produces the expected behaviors.
"""

import asyncio
import json
import logging
from dataclasses import dataclass

from langfuse import Langfuse
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Single evaluation result"""
    test_name: str
    score: float  # 0.0 to 1.0
    passed: bool
    reasoning: str
    response: str
    expected_behavior: str


@dataclass
class EvalSuite:
    """Complete evaluation suite results"""
    total_tests: int
    passed_tests: int
    failed_tests: int
    avg_score: float
    results: list[EvalResult]


class SystemPromptEvaluator:
    """
    Evaluates system prompt behavior using LLM-as-a-Judge
    """

    def __init__(
        self,
        langfuse_client: Langfuse,
        openai_client: AsyncOpenAI,
        judge_model: str = "gpt-4o",
    ):
        self.langfuse = langfuse_client
        self.openai = openai_client
        self.judge_model = judge_model
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self) -> str:
        """Get the current system prompt from Langfuse"""
        try:
            prompt = self.langfuse.get_prompt("System/Default")
            if prompt and hasattr(prompt, "prompt"):
                logger.info("Retrieved system prompt from Langfuse: System/Default")
                return prompt.prompt
            else:
                raise ValueError("System/Default prompt not found in Langfuse")
        except Exception as e:
            logger.error(f"Failed to get system prompt: {e}")
            raise

    async def _get_ai_response(self, user_message: str) -> str:
        """Get response from AI using the system prompt"""
        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini",  # Model being evaluated
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Error getting AI response: {e}")
            return f"Error: {e}"

    async def _judge_response(
        self, user_query: str, ai_response: str, expected_behavior: str, criteria: str
    ) -> tuple[float, str]:
        """Use LLM-as-a-Judge to evaluate the response"""
        judge_prompt = f"""You are evaluating an AI assistant's response for adherence to specific behavioral criteria.

USER QUERY: {user_query}

AI RESPONSE: {ai_response}

EXPECTED BEHAVIOR: {expected_behavior}

EVALUATION CRITERIA: {criteria}

Rate the response on a scale of 0.0 to 1.0 where:
- 1.0 = Perfect adherence to expected behavior
- 0.8 = Good adherence with minor issues
- 0.6 = Adequate but noticeable gaps
- 0.4 = Some adherence but significant issues
- 0.2 = Poor adherence, major problems
- 0.0 = No adherence to expected behavior

Provide your response in JSON format:
{{
    "score": 0.0-1.0,
    "reasoning": "Detailed explanation of your evaluation"
}}"""

        try:
            response = await self.openai.chat.completions.create(
                model=self.judge_model,
                messages=[{"role": "user", "content": judge_prompt}],
                temperature=0.1,  # Low temperature for consistent judging
                max_tokens=300,
            )

            result = response.choices[0].message.content or ""

            # Parse JSON response
            try:
                parsed = json.loads(result)
                return parsed["score"], parsed["reasoning"]
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                if "score" in result.lower():
                    # Try to extract score manually
                    lines = result.split("\n")
                    score_line = [l for l in lines if "score" in l.lower()]
                    if score_line:
                        score_text = score_line[0]
                        # Extract number
                        import re
                        numbers = re.findall(r"0\.\d+|1\.0", score_text)
                        if numbers:
                            return float(numbers[0]), result

                logger.warning(f"Could not parse judge response: {result}")
                return 0.5, f"Parse error: {result}"

        except Exception as e:
            logger.error(f"Error in judge evaluation: {e}")
            return 0.0, f"Judge error: {e}"

    async def run_single_eval(
        self, test_name: str, user_query: str, expected_behavior: str, criteria: str
    ) -> EvalResult:
        """Run a single evaluation test"""
        logger.info(f"Running eval: {test_name}")

        # Get AI response
        ai_response = await self._get_ai_response(user_query)

        # Judge the response
        score, reasoning = await self._judge_response(
            user_query, ai_response, expected_behavior, criteria
        )

        # Determine pass/fail (threshold: 0.7)
        passed = score >= 0.7

        return EvalResult(
            test_name=test_name,
            score=score,
            passed=passed,
            reasoning=reasoning,
            response=ai_response,
            expected_behavior=expected_behavior,
        )

    async def run_eval_suite(self) -> EvalSuite:
        """Run the complete evaluation suite"""
        logger.info("🚀 Starting System Prompt Evaluation Suite")
        logger.info("=" * 60)

        test_cases = self._get_test_cases()
        results = []

        for i, (test_name, user_query, expected_behavior, criteria) in enumerate(
            test_cases, 1
        ):
            logger.info(f"[{i}/{len(test_cases)}] {test_name}")
            result = await self._run_single_eval_with_langfuse_tracking(
                test_name, user_query, expected_behavior, criteria
            )
            results.append(result)

            # Log result
            status = "✅ PASS" if result.passed else "❌ FAIL"
            logger.info(f"{status} {test_name}: {result.score:.2f}")

        # Calculate summary stats
        passed_tests = sum(1 for r in results if r.passed)
        failed_tests = len(results) - passed_tests
        avg_score = sum(r.score for r in results) / len(results) if results else 0

        suite = EvalSuite(
            total_tests=len(results),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            avg_score=avg_score,
            results=results,
        )

        self._log_summary(suite)
        return suite

    async def _run_single_eval_with_langfuse_tracking(
        self, test_name: str, user_query: str, expected_behavior: str, criteria: str
    ) -> EvalResult:
        """Run single eval with Langfuse tracking"""
        # Create Langfuse trace for this evaluation
        trace = self.langfuse.trace(
            name="system_prompt_eval",
            metadata={
                "test_name": test_name,
                "expected_behavior": expected_behavior,
                "criteria": criteria,
            },
        )

        try:
            result = await self.run_single_eval(
                test_name, user_query, expected_behavior, criteria
            )

            # Log to Langfuse
            trace.score(
                name=test_name,
                value=result.score,
                comment=result.reasoning,
            )

            return result

        except Exception as e:
            logger.error(f"Error in eval {test_name}: {e}")
            trace.score(name=test_name, value=0.0, comment=f"Error: {e}")
            raise

    def _get_test_cases(self) -> list[tuple[str, str, str, str]]:
        """Get test cases for evaluation"""
        return [
            # Professional Communication Tests
            (
                "professional_tone",
                "What's the latest information about our product roadmap?",
                "Response uses professional, executive-appropriate language while remaining accessible",
                "Check for professional tone, business-appropriate language, no overly casual expressions",
            ),
            (
                "source_transparency",
                "Can you tell me about our Q3 performance metrics?",
                "Clearly indicates whether response is from knowledge base or general knowledge",
                "Must explicitly state information source - either from retrieved documents or general knowledge",
            ),
            (
                "accuracy_over_speculation",
                "What are the specific details of our new client contract terms?",
                "Acknowledges limitations rather than speculating or providing potentially inaccurate information",
                "Should indicate uncertainty rather than guessing, maintains intellectual honesty",
            ),
            # RAG-Specific Behavior Tests
            (
                "knowledge_base_priority",
                "Tell me about our company's remote work policy.",
                "Prioritizes organizational documents over general remote work advice",
                "Should attempt to search knowledge base first, cite specific company documents if available",
            ),
            (
                "comprehensive_citation",
                "What are our current sales projections?",
                "Provides detailed source attribution for information used",
                "Must cite specific documents, sections, or indicate when information is not available",
            ),
            (
                "context_awareness",
                "Following up on what we discussed earlier about the product launch...",
                "Acknowledges conversation context and maintains thread continuity",
                "Should reference previous conversation context appropriately or ask for clarification",
            ),
            # Advanced Features Tests
            (
                "multi_document_analysis",
                "Compare our Q2 and Q3 performance across all departments.",
                "Demonstrates ability to synthesize information from multiple sources",
                "Should indicate cross-referencing multiple documents or data sources",
            ),
            (
                "business_context_integration",
                "How should we approach the upcoming budget planning meeting?",
                "Provides business-relevant guidance considering organizational context",
                "Should offer strategic, business-focused advice appropriate for executive decision-making",
            ),
            # Agent Process Tests
            (
                "agent_process_capability",
                "I need to update our knowledge base with the new product documentation.",
                "Demonstrates awareness of automated processes and data management capabilities",
                "Should reference ability to coordinate background processes or document ingestion",
            ),
            # Error Handling Tests
            (
                "graceful_limitation_acknowledgment",
                "What's the exact ROI calculation for project X that we discussed in last week's board meeting?",
                "Gracefully handles unavailable information without making assumptions",
                "Should clearly indicate limitations, ask for clarification, avoid speculation",
            ),
            # Slack Integration Tests
            (
                "platform_appropriate_response",
                "Can you help me find the marketing budget breakdown? I need it for the presentation in 30 minutes.",
                "Provides efficient, time-conscious response appropriate for Slack context",
                "Should be concise but comprehensive, acknowledges time constraint, suggests next steps",
            ),
            # Executive Communication Tests
            (
                "executive_decision_support",
                "Should we proceed with the acquisition of Company Y based on our analysis?",
                "Provides strategic, well-sourced information suitable for executive decision-making",
                "Should offer comprehensive analysis with clear source attribution, avoid making the decision",
            ),
        ]

    def _log_summary(self, suite: EvalSuite):
        """Log evaluation summary"""
        logger.info("=" * 60)
        logger.info("📊 EVALUATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {suite.total_tests}")
        logger.info(f"Passed: {suite.passed_tests} ✅")
        logger.info(f"Failed: {suite.failed_tests} ❌")
        logger.info(f"Pass Rate: {(suite.passed_tests/suite.total_tests)*100:.1f}%")
        logger.info(f"Average Score: {suite.avg_score:.3f}")

        if suite.failed_tests > 0:
            logger.info("\n🔍 FAILED TESTS:")
            for result in suite.results:
                if not result.passed:
                    logger.info(f"❌ {result.test_name}: {result.score:.2f}")
                    logger.info(f"   Reasoning: {result.reasoning}")

        logger.info("\n🎯 RECOMMENDATIONS:")
        if suite.avg_score >= 0.8:
            logger.info("✅ System prompt is performing well!")
        elif suite.avg_score >= 0.6:
            logger.info("⚠️  System prompt needs minor improvements")
        else:
            logger.info("🚨 System prompt needs significant improvements")

        logger.info("=" * 60)


async def main():
    """Run the evaluation suite"""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    # Initialize clients
    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Run evaluation
    evaluator = SystemPromptEvaluator(langfuse, openai_client)
    suite = await evaluator.run_eval_suite()

    # Export results
    results_file = "eval_results.json"
    with open(results_file, "w"):
        json.dump(
            {
                "summary": {
                    "total_tests": suite.total_tests,
                    "passed_tests": suite.passed_tests,
                    "failed_tests": suite.failed_tests,
                    "avg_score": suite.avg_score,
                    "pass_rate": suite.passed_tests / suite.total_tests,
                },
                "results": [
                    {
                        "test_name": r.test_name,
                        "score": r.score,
                        "passed": r.passed,
                        "reasoning": r.reasoning,
                        "response": r.response,
                        "expected_behavior": r.expected_behavior,
                    }
                    for r in suite.results
                ],
            },
            indent=2,
        )

    logger.info(f"Results exported to {results_file}")


if __name__ == "__main__":
    asyncio.run(main())

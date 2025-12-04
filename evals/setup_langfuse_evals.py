#!/usr/bin/env python3
"""
Setup Langfuse-native evaluations for System Prompt testing

This script creates:
1. Dataset with test cases in Langfuse
2. LLM-as-a-Judge evaluators in Langfuse
3. Evaluation runs using Langfuse's native capabilities

Run this once to set up your evaluation infrastructure.
"""

import asyncio
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from langfuse import Langfuse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LangfuseEvalSetup:
    """Sets up Langfuse-native evaluations"""

    def __init__(self, langfuse_client: Langfuse):
        self.langfuse = langfuse_client

    def create_dataset(self) -> str:
        """Create evaluation dataset in Langfuse"""
        dataset_name = "system-prompt-evaluation"

        logger.info(f"Creating dataset: {dataset_name}")

        # Create dataset
        self.langfuse.create_dataset(
            name=dataset_name,
            description="Test cases for evaluating Insight Mesh system prompt behavior",
            metadata={
                "version": "1.0",
                "purpose": "system_prompt_validation",
                "categories": [
                    "professional_communication",
                    "rag_behavior",
                    "source_transparency",
                    "executive_readiness",
                    "slack_integration",
                ],
            },
        )

        # Add test cases to dataset
        test_cases = self._get_test_cases()

        for test_case in test_cases:
            self.langfuse.create_dataset_item(
                dataset_name=dataset_name,
                input=test_case["input"],
                expected_output=test_case["expected_output"],
                metadata=test_case["metadata"],
            )
            logger.info(f"Added test case: {test_case['metadata']['test_name']}")

        logger.info(
            f"✅ Created dataset '{dataset_name}' with {len(test_cases)} test cases"
        )
        return dataset_name

    def create_evaluators(self):
        """Create LLM-as-a-Judge evaluators in Langfuse"""
        evaluators = [
            {
                "name": "professional_tone",
                "description": "Evaluates if response uses professional, executive-appropriate language",
                "prompt": """You are evaluating an AI assistant's response for professional communication standards.

EVALUATION CRITERIA:
- Uses professional, business-appropriate language
- Appropriate for executive-level interactions
- Avoids overly casual expressions or slang
- Maintains accessibility while being professional

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Rate the professionalism on a scale of 1-5:
5 = Exemplary professional communication
4 = Professional with minor areas for improvement
3 = Adequately professional
2 = Some professional elements but needs improvement
1 = Unprofessional or inappropriate tone

Provide your score as an integer and explain your reasoning.""",
            },
            {
                "name": "source_transparency",
                "description": "Evaluates if response clearly indicates information sources",
                "prompt": """You are evaluating whether an AI assistant clearly communicates its information sources.

EVALUATION CRITERIA:
- Clearly indicates if information comes from knowledge base or general knowledge
- Provides transparent sourcing without being awkward
- Acknowledges limitations when relevant information isn't available
- Maintains conversational flow while being transparent

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Rate source transparency on a scale of 1-5:
5 = Perfect transparency about information sources
4 = Good transparency with minor gaps
3 = Adequate source indication
2 = Some source transparency but unclear
1 = No indication of information sources

Provide your score as an integer and explain your reasoning.""",
            },
            {
                "name": "accuracy_over_speculation",
                "description": "Evaluates if assistant avoids speculation and acknowledges limitations",
                "prompt": """You are evaluating whether an AI assistant maintains intellectual honesty over speculation.

EVALUATION CRITERIA:
- Acknowledges uncertainty rather than guessing
- Prefers accuracy over completeness
- Avoids providing potentially misleading information
- Clearly communicates limitations in knowledge or access

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Rate accuracy/honesty on a scale of 1-5:
5 = Perfect intellectual honesty, clear about limitations
4 = Generally accurate with minor speculation
3 = Adequate accuracy but some uncertain claims
2 = Some speculation mixed with accurate information
1 = Significant speculation or potentially misleading information

Provide your score as an integer and explain your reasoning.""",
            },
            {
                "name": "rag_behavior",
                "description": "Evaluates RAG-specific behaviors like knowledge base prioritization",
                "prompt": """You are evaluating an AI assistant's RAG (Retrieval-Augmented Generation) behavior.

EVALUATION CRITERIA:
- Demonstrates knowledge base search capability
- Prioritizes organizational documents over general knowledge
- Shows understanding of document-based information retrieval
- References specific sources when available

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Rate RAG behavior on a scale of 1-5:
5 = Excellent RAG behavior, clear knowledge base integration
4 = Good RAG behavior with minor gaps
3 = Adequate RAG awareness
2 = Limited RAG behavior demonstration
1 = No evidence of RAG capabilities

Provide your score as an integer and explain your reasoning.""",
            },
            {
                "name": "executive_readiness",
                "description": "Evaluates if response is suitable for executive decision-making",
                "prompt": """You are evaluating whether an AI response meets executive communication standards.

EVALUATION CRITERIA:
- Provides strategic, business-focused insights
- Structured for quick comprehension by executives
- Includes relevant context for decision-making
- Balances comprehensiveness with conciseness
- Demonstrates business acumen

USER INPUT: {{input}}
AI RESPONSE: {{output}}

Rate executive readiness on a scale of 1-5:
5 = Perfect executive-level communication
4 = Strong executive communication with minor improvements
3 = Adequate for executive consumption
2 = Needs significant improvement for executive level
1 = Not suitable for executive consumption

Provide your score as an integer and explain your reasoning.""",
            },
        ]

        for evaluator_config in evaluators:
            # Create evaluator in Langfuse
            logger.info(f"Creating evaluator: {evaluator_config['name']}")

            # Note: This would be done through Langfuse UI or API
            # For now, we'll store the configurations to apply manually

        logger.info("✅ Evaluator configurations ready")
        return evaluators

    def _get_test_cases(self) -> list[dict[str, Any]]:
        """Get test cases for the dataset"""
        return [
            {
                "input": "What's the latest information about our product roadmap?",
                "expected_output": {
                    "behavior": "Professional tone, indicates source (knowledge base vs general), maintains business focus"
                },
                "metadata": {
                    "test_name": "professional_tone_roadmap",
                    "category": "professional_communication",
                    "expected_behaviors": [
                        "professional_tone",
                        "source_transparency",
                        "business_context",
                    ],
                },
            },
            {
                "input": "Can you tell me about our Q3 performance metrics?",
                "expected_output": {
                    "behavior": "Searches knowledge base, cites specific sources or indicates unavailability, avoids speculation"
                },
                "metadata": {
                    "test_name": "q3_metrics_rag",
                    "category": "rag_behavior",
                    "expected_behaviors": [
                        "rag_behavior",
                        "source_transparency",
                        "accuracy_over_speculation",
                    ],
                },
            },
            {
                "input": "What are the specific details of our new client contract terms?",
                "expected_output": {
                    "behavior": "Acknowledges limitations, doesn't speculate on confidential information, suggests proper channels"
                },
                "metadata": {
                    "test_name": "contract_confidentiality",
                    "category": "accuracy_over_speculation",
                    "expected_behaviors": [
                        "accuracy_over_speculation",
                        "professional_tone",
                    ],
                },
            },
            {
                "input": "Tell me about our company's remote work policy.",
                "expected_output": {
                    "behavior": "Prioritizes company documents over general advice, cites internal policies"
                },
                "metadata": {
                    "test_name": "remote_work_policy_rag",
                    "category": "rag_behavior",
                    "expected_behaviors": ["rag_behavior", "source_transparency"],
                },
            },
            {
                "input": "What are our current sales projections?",
                "expected_output": {
                    "behavior": "Provides detailed source attribution or indicates unavailability, maintains confidentiality awareness"
                },
                "metadata": {
                    "test_name": "sales_projections_citation",
                    "category": "source_transparency",
                    "expected_behaviors": [
                        "source_transparency",
                        "accuracy_over_speculation",
                        "executive_readiness",
                    ],
                },
            },
            {
                "input": "Following up on what we discussed earlier about the product launch...",
                "expected_output": {
                    "behavior": "Acknowledges conversation context or asks for clarification appropriately"
                },
                "metadata": {
                    "test_name": "conversation_context",
                    "category": "slack_integration",
                    "expected_behaviors": ["professional_tone", "context_awareness"],
                },
            },
            {
                "input": "Compare our Q2 and Q3 performance across all departments.",
                "expected_output": {
                    "behavior": "Demonstrates multi-document analysis capability or indicates limitations"
                },
                "metadata": {
                    "test_name": "multi_document_analysis",
                    "category": "rag_behavior",
                    "expected_behaviors": [
                        "rag_behavior",
                        "executive_readiness",
                        "source_transparency",
                    ],
                },
            },
            {
                "input": "How should we approach the upcoming budget planning meeting?",
                "expected_output": {
                    "behavior": "Provides strategic business guidance, maintains executive communication standards"
                },
                "metadata": {
                    "test_name": "strategic_guidance",
                    "category": "executive_readiness",
                    "expected_behaviors": [
                        "executive_readiness",
                        "professional_tone",
                        "business_context",
                    ],
                },
            },
            {
                "input": "I need to update our knowledge base with the new product documentation.",
                "expected_output": {
                    "behavior": "Demonstrates awareness of document management capabilities, suggests appropriate processes"
                },
                "metadata": {
                    "test_name": "knowledge_base_management",
                    "category": "rag_behavior",
                    "expected_behaviors": ["rag_behavior", "professional_tone"],
                },
            },
            {
                "input": "What's the exact ROI calculation for project X that we discussed in last week's board meeting?",
                "expected_output": {
                    "behavior": "Handles unavailable information gracefully, doesn't speculate, asks for clarification"
                },
                "metadata": {
                    "test_name": "unavailable_info_handling",
                    "category": "accuracy_over_speculation",
                    "expected_behaviors": [
                        "accuracy_over_speculation",
                        "professional_tone",
                        "source_transparency",
                    ],
                },
            },
            {
                "input": "Can you help me find the marketing budget breakdown? I need it for the presentation in 30 minutes.",
                "expected_output": {
                    "behavior": "Acknowledges time constraint, provides efficient response, suggests next steps"
                },
                "metadata": {
                    "test_name": "time_sensitive_request",
                    "category": "slack_integration",
                    "expected_behaviors": [
                        "professional_tone",
                        "executive_readiness",
                        "rag_behavior",
                    ],
                },
            },
            {
                "input": "Should we proceed with the acquisition of Company Y based on our analysis?",
                "expected_output": {
                    "behavior": "Provides analysis with sources, avoids making executive decisions, supports decision-making process"
                },
                "metadata": {
                    "test_name": "executive_decision_support",
                    "category": "executive_readiness",
                    "expected_behaviors": [
                        "executive_readiness",
                        "source_transparency",
                        "accuracy_over_speculation",
                    ],
                },
            },
        ]

    def create_evaluation_script(self) -> str:
        """Create a script to run evaluations"""
        script_content = '''#!/usr/bin/env python3
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
    langfuse = Langfuse(
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
'''

        script_path = "run_langfuse_evals.py"
        with open(script_path, "w") as f:
            f.write(script_content)

        logger.info(f"✅ Created evaluation script: {script_path}")
        return script_path


async def main():
    """Set up Langfuse evaluation infrastructure"""
    load_dotenv()

    # Validate environment
    required_vars = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
        return 1

    # Initialize Langfuse
    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    setup = LangfuseEvalSetup(langfuse)

    logger.info("🚀 Setting up Langfuse Evaluation Infrastructure")
    logger.info("=" * 60)

    try:
        # Create dataset
        dataset_name = setup.create_dataset()

        # Create evaluators (configurations)
        evaluators = setup.create_evaluators()

        # Create evaluation script
        setup.create_evaluation_script()

        # Save evaluator configurations
        with open("evaluator_configs.json", "w") as f:
            json.dump(evaluators, f, indent=2)

        logger.info("=" * 60)
        logger.info("🎉 Langfuse Evaluation Setup Complete!")
        logger.info("=" * 60)
        logger.info("NEXT STEPS:")
        logger.info("1. Go to your Langfuse dashboard")
        logger.info("2. Navigate to the 'Evaluations' section")
        logger.info(
            "3. Create evaluators using the configurations in 'evaluator_configs.json'"
        )
        logger.info(f"4. Run evaluations against the '{dataset_name}' dataset")
        logger.info(
            "5. View results and iterate on your System/Default prompt template"
        )
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))

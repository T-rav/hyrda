"""Prompt evaluations for research planner node.

These tests verify that the planner prompt:
1. Creates appropriate research plans for diverse topics
2. Generates relevant research tasks
3. Works for non-company topics
4. Produces structured, actionable plans
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from agents.research.nodes.research_planner import create_research_plan
from agents.research.state import ResearchAgentState


@pytest.fixture
def mock_settings():
    """Mock settings."""
    settings = MagicMock()
    settings.llm = MagicMock()
    settings.llm.model = "gpt-4o"
    settings.llm.api_key = "test-key"
    return settings


def create_mock_plan_response(strategy: str, num_tasks: int = 5) -> AIMessage:
    """Create mock LLM response with research plan."""
    tasks = [
        {
            "description": f"Research task {i + 1}",
            "priority": "high" if i < 2 else "medium",
            "dependencies": [] if i == 0 else [f"task_{i - 1}"],
        }
        for i in range(num_tasks)
    ]

    plan = {
        "strategy": strategy,
        "tasks": tasks,
        "report_structure": "Executive Summary, Key Findings, Detailed Analysis, Conclusion",
    }

    response = MagicMock(spec=AIMessage)
    response.content = json.dumps(plan)
    return response


class TestPlannerPromptBehavior:
    """Test that planner prompt guides correct LLM behavior."""

    @pytest.mark.asyncio
    async def test_prompt_creates_plan_for_company_topic(self, mock_settings):
        """Eval: Verify planner creates appropriate plan for company research."""
        state: ResearchAgentState = {
            "query": "Research Costco's business model",
            "research_depth": "standard",
        }

        mock_response = create_mock_plan_response(
            "Comprehensive analysis of Costco's business model focusing on revenue streams, competitive advantages, and market position."
        )

        with patch("agents.research.nodes.research_planner.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_response):
                result = await create_research_plan(state)

                # Verify plan was created
                assert "research_plan" in result
                assert "research_tasks" in result
                assert len(result["research_tasks"]) > 0

    @pytest.mark.asyncio
    async def test_prompt_creates_plan_for_technical_topic(self, mock_settings):
        """Eval: Verify planner creates appropriate plan for technical topics."""
        state: ResearchAgentState = {
            "query": "What are our microservices deployment best practices?",
            "research_depth": "deep",
        }

        mock_response = create_mock_plan_response(
            "Comprehensive analysis of microservices deployment practices, infrastructure, and operational procedures."
        )

        with patch("agents.research.nodes.research_planner.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_response):
                result = await create_research_plan(state)

                # Verify plan doesn't assume company research
                assert "research_plan" in result
                assert "research_tasks" in result

                # Plan should be created successfully for non-company topic
                assert len(result["research_tasks"]) > 0

    @pytest.mark.asyncio
    async def test_prompt_includes_query_and_depth(self, mock_settings):
        """Eval: Verify prompt includes query and research depth."""
        state: ResearchAgentState = {
            "query": "Analyze our GDPR compliance requirements",
            "research_depth": "comprehensive",
        }

        captured_prompt = None

        async def capture_prompt(messages):
            nonlocal captured_prompt
            captured_prompt = messages[0].content
            return create_mock_plan_response("Legal compliance analysis.")

        with patch("agents.research.nodes.research_planner.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", side_effect=capture_prompt):
                await create_research_plan(state)

                # Verify prompt included query and depth
                assert captured_prompt is not None
                assert state["query"] in captured_prompt
                assert state["research_depth"] in captured_prompt

    @pytest.mark.asyncio
    async def test_prompt_requests_structured_output(self, mock_settings):
        """Eval: Verify prompt requests structured JSON output."""
        state: ResearchAgentState = {
            "query": "Research our remote work policy",
            "research_depth": "standard",
        }

        captured_prompt = None

        async def capture_prompt(messages):
            nonlocal captured_prompt
            captured_prompt = messages[0].content
            return create_mock_plan_response("HR policy analysis.")

        with patch("agents.research.nodes.research_planner.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", side_effect=capture_prompt):
                await create_research_plan(state)

                # Verify prompt requests structured format
                assert captured_prompt is not None
                assert "JSON" in captured_prompt or "json" in captured_prompt
                assert "strategy" in captured_prompt
                assert "tasks" in captured_prompt
                assert "report_structure" in captured_prompt

    @pytest.mark.asyncio
    async def test_prompt_example_is_generic(self, mock_settings):
        """Eval: Verify prompt example is topic-agnostic."""
        state: ResearchAgentState = {
            "query": "Research our product development process",
            "research_depth": "standard",
        }

        captured_prompt = None

        async def capture_prompt(messages):
            nonlocal captured_prompt
            captured_prompt = messages[0].content
            return create_mock_plan_response("Product development analysis.")

        with patch("agents.research.nodes.research_planner.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", side_effect=capture_prompt):
                await create_research_plan(state)

                # Verify example doesn't bias toward companies
                assert captured_prompt is not None

                # Should NOT have company-specific example
                assert "Q4 2023 financial performance" not in captured_prompt
                assert "company's Q4" not in captured_prompt.lower()

                # Should have generic example
                assert "internal documentation" in captured_prompt.lower() or "key findings" in captured_prompt.lower()


class TestPlannerPromptDiverseTopics:
    """Test that planner prompt works across diverse research domains."""

    @pytest.mark.parametrize(
        "query,expected_domain",
        [
            ("Research Tesla's market strategy", "Business"),
            ("What are our API design best practices?", "Technical"),
            ("Analyze our employee onboarding process", "HR"),
            ("What are our data privacy policies?", "Legal/Compliance"),
            ("Research our product feature roadmap", "Product"),
            ("What security audits do we perform?", "Security"),
        ],
    )
    @pytest.mark.asyncio
    async def test_prompt_works_across_domains(
        self, query, expected_domain, mock_settings
    ):
        """Eval: Verify prompt creates plans for diverse topics."""
        state: ResearchAgentState = {
            "query": query,
            "research_depth": "standard",
        }

        mock_response = create_mock_plan_response(
            f"Comprehensive analysis of {expected_domain} topic."
        )

        with patch("agents.research.nodes.research_planner.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_response):
                result = await create_research_plan(state)

                # Verify plan was created for any domain
                assert "research_plan" in result
                assert "research_tasks" in result
                assert len(result["research_tasks"]) > 0

                # Verify tasks have required fields
                for task in result["research_tasks"]:
                    assert hasattr(task, "description")
                    assert hasattr(task, "priority")
                    assert hasattr(task, "dependencies")

    @pytest.mark.asyncio
    async def test_prompt_guides_comprehensive_task_creation(self, mock_settings):
        """Eval: Verify prompt requests comprehensive task breakdown."""
        state: ResearchAgentState = {
            "query": "Research our cloud infrastructure strategy",
            "research_depth": "deep",
        }

        captured_prompt = None

        async def capture_prompt(messages):
            nonlocal captured_prompt
            captured_prompt = messages[0].content
            return create_mock_plan_response("Infrastructure analysis.", num_tasks=15)

        with patch("agents.research.nodes.research_planner.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", side_effect=capture_prompt):
                result = await create_research_plan(state)

                # Verify prompt requests multiple tasks
                assert captured_prompt is not None
                assert "15-20 specific tasks" in captured_prompt or "tasks" in captured_prompt

                # Should create multiple tasks
                assert len(result["research_tasks"]) >= 5

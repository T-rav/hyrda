"""Prompt evaluations for researcher node.

These tests verify that the researcher prompt guides the LLM to:
1. Use tools in the correct order (internal search first)
2. Work for diverse research topics (not just companies)
3. Cite sources appropriately
4. Make appropriate tool calls based on the task
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from agents.research.nodes.researcher import researcher
from agents.research.state import ResearcherState, ResearchTask


def create_research_task(
    description: str,
    priority: str = "high",
    task_id: str = "task_1",
) -> ResearchTask:
    """Helper to create valid ResearchTask with all required fields."""
    return ResearchTask(
        task_id=task_id,
        description=description,
        priority=priority,
        status="pending",
        dependencies=[],
        findings=None,
        created_at=datetime.now().isoformat(),
        completed_at=None,
    )


@pytest.fixture
def mock_llm_response_with_tools():
    """Mock LLM response that includes tool calls."""
    response = MagicMock(spec=AIMessage)
    response.content = "I'll search the internal knowledge base first."
    response.tool_calls = [
        {
            "id": "call_123",
            "function": {
                "name": "internal_search_tool",
                "arguments": {"query": "test query", "effort": "medium"},
            },
        }
    ]
    return response


@pytest.fixture
def mock_settings():
    """Mock settings."""
    settings = MagicMock()
    settings.llm = MagicMock()
    settings.llm.model = "gpt-4o"
    settings.llm.api_key = "test-key"
    return settings


class TestResearcherPromptBehavior:
    """Test that researcher prompt guides correct LLM behavior."""

    @pytest.mark.asyncio
    async def test_prompt_guides_internal_search_first_company_topic(
        self, mock_llm_response_with_tools, mock_settings
    ):
        """Eval: Verify prompt guides LLM to use internal search first (company topic)."""
        state: ResearcherState = {
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "current_task": create_research_task(
                description="Research Costco's business model",
                priority="high",
            ),
            "compressed_research": "",
            "raw_notes": [],
            "research_topic": "Costco",
            "focus_area": "business model",
        }

        with patch("agents.research.nodes.researcher.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_llm_response_with_tools):
                result = await researcher(state)

                # Verify tool was called
                assert result["tool_call_iterations"] == 1
                assert len(result["researcher_messages"]) > 0

                # Check that the prompt emphasized internal search
                messages = result["researcher_messages"]
                system_msg = str(messages[0].content)
                assert "internal_search_tool" in system_msg.lower()
                assert "ALWAYS START HERE" in system_msg

    @pytest.mark.asyncio
    async def test_prompt_works_for_technical_topic(
        self, mock_llm_response_with_tools, mock_settings
    ):
        """Eval: Verify prompt works for technical (non-company) topics."""
        state: ResearcherState = {
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "current_task": create_research_task(
                description="Research our microservices deployment best practices",
                priority="high",
            ),
            "compressed_research": "",
            "raw_notes": [],
            "research_topic": "Microservices",
            "focus_area": "deployment",
        }

        with patch("agents.research.nodes.researcher.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_llm_response_with_tools):
                result = await researcher(state)

                # Verify the prompt doesn't force company-specific behavior
                messages = result["researcher_messages"]
                system_msg = str(messages[0].content)

                # Should NOT have company-specific language
                assert "companies/people" not in system_msg.lower()
                assert "relationships (companies" not in system_msg.lower()

                # Should have generic guidance
                assert "internal knowledge base" in system_msg.lower()
                assert "documents, policies, past work" in system_msg.lower()

    @pytest.mark.asyncio
    async def test_prompt_includes_tool_guidance(self, mock_settings):
        """Eval: Verify prompt provides clear tool usage guidance."""
        state: ResearcherState = {
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "current_task": create_research_task(
                description="Research our GDPR compliance requirements",
                priority="high",
            ),
            "compressed_research": "",
            "raw_notes": [],
            "research_topic": "GDPR",
            "focus_area": "compliance",
        }

        mock_response = MagicMock(spec=AIMessage)
        mock_response.content = "Researching compliance requirements."
        mock_response.tool_calls = []

        with patch("agents.research.nodes.researcher.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_response):
                result = await researcher(state)

                messages = result["researcher_messages"]
                system_msg = str(messages[0].content)

                # Verify tool guidance is present and clear
                assert "Research Workflow:" in system_msg
                assert "internal_search_tool" in system_msg
                assert "sec_query" in system_msg
                assert "web_search" in system_msg

                # Verify priority is documented (effort levels explanation was removed from prompt)
                assert "priority" in system_msg.lower() or "high" in system_msg

    @pytest.mark.asyncio
    async def test_prompt_emphasizes_source_citation(self, mock_settings):
        """Eval: Verify prompt guides LLM to cite sources."""
        state: ResearcherState = {
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "current_task": create_research_task(
                description="Research our remote work policy",
                priority="medium",
            ),
            "compressed_research": "",
            "raw_notes": [],
            "research_topic": "HR Policies",
            "focus_area": "remote work",
        }

        mock_response = MagicMock(spec=AIMessage)
        mock_response.content = "I'll search for remote work policies."
        mock_response.tool_calls = []

        with patch("agents.research.nodes.researcher.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_response):
                result = await researcher(state)

                messages = result["researcher_messages"]
                system_msg = str(messages[0].content)

                # Verify citation guidance
                assert "cite" in system_msg.lower() or "sources" in system_msg.lower()
                assert "internal" in system_msg.lower()

    @pytest.mark.asyncio
    async def test_prompt_format_includes_task_details(self, mock_settings):
        """Eval: Verify prompt includes task description and priority."""
        task = create_research_task(
            description="Analyze our AI implementation strategy",
            priority="high",
        )

        state: ResearcherState = {
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "current_task": task,
            "compressed_research": "",
            "raw_notes": [],
            "research_topic": "AI Strategy",
            "focus_area": "implementation",
        }

        mock_response = MagicMock(spec=AIMessage)
        mock_response.content = "Starting research on AI strategy."
        mock_response.tool_calls = []

        with patch("agents.research.nodes.researcher.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_response):
                result = await researcher(state)

                messages = result["researcher_messages"]
                system_msg = str(messages[0].content)

                # Verify task details are included
                assert task.description in system_msg
                assert task.priority in system_msg


class TestResearcherPromptDiverseTopics:
    """Test that researcher prompt works across diverse research domains."""

    @pytest.mark.parametrize(
        "task_description,topic",
        [
            ("Research Acme Corp's revenue model", "Company Analysis"),
            ("What are our microservices best practices?", "Technical Documentation"),
            ("Analyze our hiring process", "HR Processes"),
            ("What are GDPR compliance requirements?", "Legal Compliance"),
            ("Research our product roadmap", "Product Strategy"),
            ("What security protocols do we follow?", "Security"),
        ],
    )
    @pytest.mark.asyncio
    async def test_prompt_works_across_domains(
        self, task_description, topic, mock_settings
    ):
        """Eval: Verify prompt works for diverse research topics."""
        state: ResearcherState = {
            "researcher_messages": [],
            "tool_call_iterations": 0,
            "current_task": create_research_task(
                description=task_description,
                priority="medium",
            ),
            "compressed_research": "",
            "raw_notes": [],
            "research_topic": topic,
            "focus_area": "",
        }

        mock_response = MagicMock(spec=AIMessage)
        mock_response.content = f"Researching {topic}."
        mock_response.tool_calls = []

        with patch("agents.research.nodes.researcher.Settings", return_value=mock_settings):
            with patch.object(ChatOpenAI, "ainvoke", return_value=mock_response):
                result = await researcher(state)

                messages = result["researcher_messages"]
                system_msg = str(messages[0].content)

                # Verify prompt is topic-agnostic
                assert task_description in system_msg
                assert "internal" in system_msg.lower()

                # Should not fail or produce company-specific biases
                assert "researcher_messages" in result

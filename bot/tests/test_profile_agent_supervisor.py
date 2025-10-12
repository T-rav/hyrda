"""Tests for ProfileAgent supervisor nodes."""

import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import END
from langgraph.types import Command

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.company_profile.nodes.supervisor import (
    execute_researcher,
    supervisor,
    supervisor_tools,
)


class TestSupervisorNode:
    """Tests for supervisor node"""

    @pytest.mark.asyncio
    async def test_supervisor_with_tool_calls(self):
        """Test supervisor delegating research tasks"""
        state = {
            "research_brief": "Research Tesla electric vehicles",
            "profile_type": "company",
            "research_iterations": 0,
            "notes": [],
            "supervisor_messages": [],
        }

        config = {
            "configurable": {
                "max_concurrent_research_units": 3,
                "max_researcher_iterations": 5,
            }
        }

        # Mock LLM response with ConductResearch tool calls
        mock_response = Mock()
        mock_response.content = "Let me delegate research tasks"
        mock_response.tool_calls = [
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Tesla market share"},
                "id": "tc_1",
            },
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Tesla products"},
                "id": "tc_2",
            },
        ]

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await supervisor(state, config)

        assert isinstance(result, Command)
        assert result.goto == "supervisor_tools"
        assert result.update["research_iterations"] == 1

    @pytest.mark.asyncio
    async def test_supervisor_research_complete(self):
        """Test supervisor signaling research complete"""
        state = {
            "research_brief": "Research brief",
            "profile_type": "company",
            "research_iterations": 3,
            "notes": ["Note 1", "Note 2", "Note 3"],
            "supervisor_messages": [],
        }

        config = {
            "configurable": {
                "max_concurrent_research_units": 3,
                "max_researcher_iterations": 5,
            }
        }

        # Mock LLM response with ResearchComplete
        mock_response = Mock()
        mock_response.content = "Research is complete"
        mock_response.tool_calls = [
            {
                "name": "ResearchComplete",
                "args": {"research_summary": "All research done"},
                "id": "tc_complete",
            }
        ]

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await supervisor(state, config)

        assert isinstance(result, Command)
        assert result.goto == "supervisor_tools"

    @pytest.mark.asyncio
    async def test_supervisor_no_tool_calls(self):
        """Test supervisor ending without tool calls"""
        state = {
            "research_brief": "Research brief",
            "profile_type": "company",
            "research_iterations": 0,
            "notes": [],
            "supervisor_messages": [],
        }

        config = {
            "configurable": {
                "max_concurrent_research_units": 3,
                "max_researcher_iterations": 5,
            }
        }

        # Mock LLM response without tool calls
        mock_response = Mock()
        mock_response.content = "All tasks delegated"
        mock_response.tool_calls = []

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await supervisor(state, config)

        assert isinstance(result, Command)
        assert result.goto == END

    @pytest.mark.asyncio
    async def test_supervisor_missing_research_brief(self):
        """Test supervisor with missing research brief"""
        state = {
            "research_brief": "",  # Missing
            "profile_type": "company",
            "research_iterations": 0,
            "notes": [],
            "supervisor_messages": [],
        }

        config = {"configurable": {}}

        result = await supervisor(state, config)

        assert isinstance(result, Command)
        assert result.goto == END
        assert "error" in result.update["final_report"].lower()

    @pytest.mark.asyncio
    async def test_supervisor_exception_handling(self):
        """Test supervisor handles exceptions"""
        state = {
            "research_brief": "Brief",
            "profile_type": "company",
            "research_iterations": 0,
            "notes": [],
            "supervisor_messages": [],
        }

        config = {"configurable": {}}

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            mock_llm = Mock()
            mock_llm_with_tools = Mock()
            mock_llm_with_tools.ainvoke = AsyncMock(side_effect=Exception("API error"))
            mock_llm.bind_tools = Mock(return_value=mock_llm_with_tools)
            mock_chat.return_value = mock_llm

            result = await supervisor(state, config)

        assert isinstance(result, Command)
        assert result.goto == END


class TestSupervisorToolsNode:
    """Tests for supervisor_tools node"""

    @pytest.mark.asyncio
    async def test_supervisor_tools_conduct_research(self):
        """Test executing ConductResearch tool calls"""
        # Mock AIMessage with tool calls
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Tesla financials"},
                "id": "tc_1",
            },
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Tesla competition"},
                "id": "tc_2",
            },
        ]

        state = {
            "research_brief": "Research Tesla",
            "profile_type": "company",
            "research_iterations": 1,
            "notes": [],
            "raw_notes": [],
            "supervisor_messages": [HumanMessage(content="Start"), mock_ai_message],
        }

        config = {
            "configurable": {
                "max_concurrent_research_units": 5,
                "max_researcher_iterations": 10,
            }
        }

        # Mock researcher subgraph
        mock_researcher_graph = Mock()
        mock_researcher_graph.ainvoke = AsyncMock(
            return_value={
                "compressed_research": "Compressed findings",
                "raw_notes": ["Raw note 1"],
            }
        )

        with patch(
            "agents.company_profile.nodes.graph_builder.build_researcher_subgraph",
            return_value=mock_researcher_graph,
        ):
            result = await supervisor_tools(state, config)

        # Should execute both research tasks
        assert mock_researcher_graph.ainvoke.call_count == 2

        assert isinstance(result, Command)
        assert result.goto == "supervisor"
        assert len(result.update["notes"]) == 2
        assert "Compressed findings" in result.update["notes"]

    @pytest.mark.asyncio
    async def test_supervisor_tools_think_tool(self):
        """Test executing think_tool"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "think_tool",
                "args": {"reflection": "I need to gather more data"},
                "id": "tc_think",
            },
            {
                "name": "ConductResearch",
                "args": {"research_topic": "More research"},
                "id": "tc_research",
            },
        ]

        state = {
            "research_brief": "Brief",
            "profile_type": "company",
            "research_iterations": 1,
            "notes": [],
            "raw_notes": [],
            "supervisor_messages": [mock_ai_message],
        }

        config = {
            "configurable": {
                "max_concurrent_research_units": 5,
                "max_researcher_iterations": 10,
            }
        }

        mock_researcher_graph = Mock()
        mock_researcher_graph.ainvoke = AsyncMock(
            return_value={
                "compressed_research": "Research result",
                "raw_notes": ["Note"],
            }
        )

        with patch(
            "agents.company_profile.nodes.graph_builder.build_researcher_subgraph",
            return_value=mock_researcher_graph,
        ):
            result = await supervisor_tools(state, config)

        # Think tool should be executed, research should be delegated
        assert isinstance(result, Command)
        assert result.goto == "supervisor"

    @pytest.mark.asyncio
    async def test_supervisor_tools_research_complete_signal(self):
        """Test ResearchComplete signal stops execution"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "ResearchComplete",
                "args": {"research_summary": "Done"},
                "id": "tc_complete",
            }
        ]

        state = {
            "research_brief": "Brief",
            "profile_type": "company",
            "research_iterations": 2,
            "notes": ["Note 1"],
            "raw_notes": [],
            "supervisor_messages": [mock_ai_message],
        }

        config = {"configurable": {}}

        result = await supervisor_tools(state, config)

        assert isinstance(result, Command)
        assert result.goto == END

    @pytest.mark.asyncio
    async def test_supervisor_tools_max_iterations_reached(self):
        """Test max iterations stops execution"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "ConductResearch",
                "args": {"research_topic": "More research"},
                "id": "tc_1",
            }
        ]

        state = {
            "research_brief": "Brief",
            "profile_type": "company",
            "research_iterations": 10,  # Max reached
            "notes": [],
            "raw_notes": [],
            "supervisor_messages": [mock_ai_message],
        }

        config = {
            "configurable": {
                "max_researcher_iterations": 10,
            }
        }

        result = await supervisor_tools(state, config)

        assert isinstance(result, Command)
        assert result.goto == END

    @pytest.mark.asyncio
    async def test_supervisor_tools_limits_concurrent_research(self):
        """Test concurrent research limit is enforced"""
        # Create 10 research tasks
        tool_calls = [
            {
                "name": "ConductResearch",
                "args": {"research_topic": f"Topic {i}"},
                "id": f"tc_{i}",
            }
            for i in range(10)
        ]

        mock_ai_message = Mock()
        mock_ai_message.tool_calls = tool_calls

        state = {
            "research_brief": "Brief",
            "profile_type": "company",
            "research_iterations": 1,
            "notes": [],
            "raw_notes": [],
            "supervisor_messages": [mock_ai_message],
        }

        config = {
            "configurable": {
                "max_concurrent_research_units": 3,  # Limit to 3
                "max_researcher_iterations": 10,
            }
        }

        mock_researcher_graph = Mock()
        mock_researcher_graph.ainvoke = AsyncMock(
            return_value={
                "compressed_research": "Result",
                "raw_notes": ["Note"],
            }
        )

        with patch(
            "agents.company_profile.nodes.graph_builder.build_researcher_subgraph",
            return_value=mock_researcher_graph,
        ):
            await supervisor_tools(state, config)

        # Should only execute 3 tasks (limit)
        assert mock_researcher_graph.ainvoke.call_count == 3

    @pytest.mark.asyncio
    async def test_supervisor_tools_no_tool_calls(self):
        """Test with no tool calls in message"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = []

        state = {
            "research_brief": "Brief",
            "profile_type": "company",
            "research_iterations": 1,
            "notes": [],
            "raw_notes": [],
            "supervisor_messages": [mock_ai_message],
        }

        config = {"configurable": {}}

        result = await supervisor_tools(state, config)

        assert isinstance(result, Command)
        assert result.goto == END

    @pytest.mark.asyncio
    async def test_supervisor_tools_researcher_error_handling(self):
        """Test handling researcher errors"""
        mock_ai_message = Mock()
        mock_ai_message.tool_calls = [
            {
                "name": "ConductResearch",
                "args": {"research_topic": "Failing topic"},
                "id": "tc_fail",
            }
        ]

        state = {
            "research_brief": "Brief",
            "profile_type": "company",
            "research_iterations": 1,
            "notes": [],
            "raw_notes": [],
            "supervisor_messages": [mock_ai_message],
        }

        config = {
            "configurable": {
                "max_concurrent_research_units": 5,
                "max_researcher_iterations": 10,
            }
        }

        # Mock researcher that fails
        mock_researcher_graph = Mock()
        mock_researcher_graph.ainvoke = AsyncMock(
            side_effect=Exception("Researcher failed")
        )

        with patch(
            "agents.company_profile.nodes.graph_builder.build_researcher_subgraph",
            return_value=mock_researcher_graph,
        ):
            result = await supervisor_tools(state, config)

        # Should handle error gracefully
        assert isinstance(result, Command)
        assert result.goto == "supervisor"


class TestExecuteResearcher:
    """Tests for execute_researcher helper function"""

    @pytest.mark.asyncio
    async def test_execute_researcher_success(self):
        """Test successful researcher execution"""
        mock_graph = Mock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "compressed_research": "Compressed findings",
                "raw_notes": ["Note 1", "Note 2"],
            }
        )

        result = await execute_researcher(
            researcher_graph=mock_graph,
            research_topic="Tesla market analysis",
            profile_type="company",
            tool_id="tc_123",
            config={"configurable": {}},
        )

        assert isinstance(result["tool_result"], ToolMessage)
        assert result["tool_result"].content == "Compressed findings"
        assert result["tool_result"].tool_call_id == "tc_123"
        assert result["compressed_research"] == "Compressed findings"
        assert result["raw_notes"] == ["Note 1", "Note 2"]

    @pytest.mark.asyncio
    async def test_execute_researcher_no_results(self):
        """Test researcher with no results"""
        mock_graph = Mock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "compressed_research": "",
                "raw_notes": [],
            }
        )

        result = await execute_researcher(
            researcher_graph=mock_graph,
            research_topic="Empty research",
            profile_type="company",
            tool_id="tc_empty",
            config={"configurable": {}},
        )

        assert result["tool_result"].content == "No research results"
        assert result["compressed_research"] == ""
        assert result["raw_notes"] == []

    @pytest.mark.asyncio
    async def test_execute_researcher_exception(self):
        """Test researcher exception handling"""
        mock_graph = Mock()
        mock_graph.ainvoke = AsyncMock(side_effect=Exception("Graph execution failed"))

        result = await execute_researcher(
            researcher_graph=mock_graph,
            research_topic="Failing topic",
            profile_type="company",
            tool_id="tc_fail",
            config={"configurable": {}},
        )

        assert "Research error" in result["tool_result"].content
        assert result["compressed_research"] == ""
        assert result["raw_notes"] == []

    @pytest.mark.asyncio
    async def test_execute_researcher_with_config(self):
        """Test researcher receives correct config"""
        mock_graph = Mock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "compressed_research": "Results",
                "raw_notes": [],
            }
        )

        config = {
            "configurable": {
                "llm_service": Mock(),
                "search_api": "tavily",
            }
        }

        await execute_researcher(
            researcher_graph=mock_graph,
            research_topic="Topic",
            profile_type="company",
            tool_id="tc_1",
            config=config,
        )

        # Verify config was passed to graph
        call_args = mock_graph.ainvoke.call_args
        assert call_args[0][1] == config  # Second argument should be config

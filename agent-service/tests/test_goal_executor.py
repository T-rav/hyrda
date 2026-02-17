"""Tests for goal executor subgraph."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.goal_executor.nodes.checker import check_progress, check_router
from agents.goal_executor.nodes.executor import create_step_executor
from agents.goal_executor.nodes.graph_builder import build_goal_executor, save_state
from agents.goal_executor.nodes.planner import create_plan
from agents.goal_executor.state import (
    GoalExecutorState,
    GoalPlan,
    GoalStatus,
    GoalStep,
    StepStatus,
)


class TestGoalExecutorState:
    """Tests for state definitions."""

    def test_goal_step_creation(self):
        """Test GoalStep model creation."""
        step = GoalStep(
            id="step-1",
            name="Research companies",
            prompt="Find tech companies in SF",
        )
        assert step.id == "step-1"
        assert step.status == StepStatus.PENDING
        assert step.depends_on == []
        assert step.attempts == 0

    def test_goal_step_with_dependencies(self):
        """Test GoalStep with dependencies."""
        step = GoalStep(
            id="step-2",
            name="Analyze results",
            prompt="Analyze the found companies",
            depends_on=["step-1"],
        )
        assert step.depends_on == ["step-1"]

    def test_goal_plan_creation(self):
        """Test GoalPlan model creation."""
        plan = GoalPlan(
            plan_id="plan-123",
            goal="Research competitors",
            steps=[
                GoalStep(id="step-1", name="Search", prompt="Search for companies"),
                GoalStep(
                    id="step-2",
                    name="Analyze",
                    prompt="Analyze results",
                    depends_on=["step-1"],
                ),
            ],
        )
        assert plan.plan_id == "plan-123"
        assert len(plan.steps) == 2
        assert plan.steps[1].depends_on == ["step-1"]


class TestPlanner:
    """Tests for the planner node."""

    @pytest.mark.asyncio
    async def test_create_plan_from_goal(self):
        """Test plan creation from a goal."""
        from agents.goal_executor.nodes.planner import GeneratedPlan, PlanStep

        # Create a proper GeneratedPlan instance
        mock_plan = GeneratedPlan(
            steps=[
                PlanStep(name="Search", prompt="Search for data", depends_on=[]),
                PlanStep(name="Analyze", prompt="Analyze data", depends_on=["Search"]),
            ],
            reasoning="Two-step approach",
        )

        with patch(
            "agents.goal_executor.nodes.planner.ChatAnthropic"
        ) as mock_llm_class:
            mock_llm = MagicMock()
            mock_structured = MagicMock()
            mock_structured.ainvoke = AsyncMock(return_value=mock_plan)
            mock_llm.with_structured_output.return_value = mock_structured
            mock_llm_class.return_value = mock_llm

            state: GoalExecutorState = {"goal": "Research AI companies"}
            result = await create_plan(state)

            assert "plan" in result
            assert result["status"] == GoalStatus.RUNNING

    @pytest.mark.asyncio
    async def test_create_plan_resumes_from_persistent_state(self):
        """Test that planning resumes from persistent state."""
        state: GoalExecutorState = {
            "goal": "Research companies",
            "persistent_state": {
                "plan": {
                    "plan_id": "plan-existing",
                    "goal": "Research companies",
                    "steps": [
                        {
                            "id": "step-1",
                            "name": "Search",
                            "prompt": "Search",
                            "depends_on": [],
                            "status": "pending",
                        },
                    ],
                    "created_at": "2024-01-01T00:00:00Z",
                }
            },
        }

        result = await create_plan(state)

        assert result["plan"].plan_id == "plan-existing"
        assert result["plan"].source == "resume"


class TestExecutor:
    """Tests for the executor node."""

    def test_create_step_executor_with_defaults(self):
        """Test creating executor with default tools."""
        executor = create_step_executor()
        assert callable(executor)

    def test_create_step_executor_with_custom_tools(self):
        """Test creating executor with custom tools."""
        from langchain_core.tools import tool

        @tool
        def custom_tool(query: str) -> str:
            """Custom tool."""
            return f"Result: {query}"

        executor = create_step_executor(
            tools=[custom_tool],
            system_prompt="Custom prompt",
        )
        assert callable(executor)

    @pytest.mark.asyncio
    async def test_execute_step_no_plan(self):
        """Test executor returns error when no plan."""
        executor = create_step_executor()
        state: GoalExecutorState = {"goal": "Test"}

        result = await executor(state)
        assert "error_message" in result
        assert "No plan" in result["error_message"]

    @pytest.mark.asyncio
    async def test_execute_step_finds_ready_step(self):
        """Test executor finds and executes ready step."""
        plan = GoalPlan(
            plan_id="plan-test",
            goal="Test goal",
            steps=[
                GoalStep(id="step-1", name="First", prompt="Do first thing"),
            ],
        )

        with patch(
            "agents.goal_executor.nodes.executor.ChatAnthropic"
        ) as mock_llm_class:
            mock_response = MagicMock()
            mock_response.content = "Step completed successfully"
            mock_response.tool_calls = None

            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value.ainvoke = AsyncMock(
                return_value=mock_response
            )
            mock_llm_class.return_value = mock_llm

            executor = create_step_executor()
            state: GoalExecutorState = {
                "goal": "Test goal",
                "plan": plan,
                "completed_results": {},
            }

            result = await executor(state)

            assert "completed_results" in result
            assert "step-1" in result["completed_results"]


class TestChecker:
    """Tests for the checker node."""

    @pytest.mark.asyncio
    async def test_check_progress_no_plan(self):
        """Test checker returns failed when no plan."""
        state: GoalExecutorState = {"goal": "Test"}

        result = await check_progress(state)
        assert result["status"] == GoalStatus.FAILED
        assert "No plan" in result["error_message"]

    @pytest.mark.asyncio
    async def test_check_progress_all_succeeded(self):
        """Test checker marks complete when all steps succeed."""
        plan = GoalPlan(
            plan_id="plan-test",
            goal="Test goal",
            steps=[
                GoalStep(
                    id="step-1",
                    name="First",
                    prompt="Do first",
                    status=StepStatus.SUCCEEDED,
                ),
                GoalStep(
                    id="step-2",
                    name="Second",
                    prompt="Do second",
                    status=StepStatus.SUCCEEDED,
                ),
            ],
        )

        state: GoalExecutorState = {
            "goal": "Test goal",
            "plan": plan,
            "completed_results": {"step-1": "Result 1", "step-2": "Result 2"},
            "iteration_count": 0,
            "max_iterations": 10,
        }

        result = await check_progress(state)

        assert result["status"] == GoalStatus.COMPLETED
        assert "Goal achieved" in result["final_outcome"]

    @pytest.mark.asyncio
    async def test_check_progress_max_iterations(self):
        """Test checker fails when max iterations reached."""
        plan = GoalPlan(
            plan_id="plan-test",
            goal="Test goal",
            steps=[
                GoalStep(
                    id="step-1",
                    name="First",
                    prompt="Do first",
                    status=StepStatus.PENDING,
                ),
            ],
        )

        state: GoalExecutorState = {
            "goal": "Test goal",
            "plan": plan,
            "completed_results": {},
            "iteration_count": 9,  # Will become 10
            "max_iterations": 10,
        }

        result = await check_progress(state)

        assert result["status"] == GoalStatus.FAILED
        assert "Max iterations" in result["error_message"]

    def test_check_router_completed(self):
        """Test router returns end for completed status."""
        state: GoalExecutorState = {
            "goal": "Test",
            "status": GoalStatus.COMPLETED,
        }

        result = check_router(state)
        assert result == "end"

    def test_check_router_failed(self):
        """Test router returns end for failed status."""
        state: GoalExecutorState = {
            "goal": "Test",
            "status": GoalStatus.FAILED,
        }

        result = check_router(state)
        assert result == "end"

    def test_check_router_continue(self):
        """Test router returns execute when pending steps exist."""
        plan = GoalPlan(
            plan_id="plan-test",
            goal="Test goal",
            steps=[
                GoalStep(
                    id="step-1",
                    name="First",
                    prompt="Do first",
                    status=StepStatus.PENDING,
                ),
            ],
        )

        state: GoalExecutorState = {
            "goal": "Test",
            "status": GoalStatus.RUNNING,
            "plan": plan,
        }

        result = check_router(state)
        assert result == "execute"


class TestSaveState:
    """Tests for state persistence."""

    @pytest.mark.asyncio
    async def test_save_state_persists_plan(self):
        """Test that save_state persists the plan."""
        plan = GoalPlan(
            plan_id="plan-test",
            goal="Test goal",
            steps=[
                GoalStep(
                    id="step-1",
                    name="First",
                    prompt="Do first",
                    status=StepStatus.SUCCEEDED,
                ),
            ],
        )

        state: GoalExecutorState = {
            "goal": "Test",
            "plan": plan,
            "completed_results": {"step-1": "Done"},
            "status": GoalStatus.COMPLETED,
            "final_outcome": "Success",
        }

        result = await save_state(state)

        assert "persistent_state" in result
        assert result["persistent_state"]["plan"]["plan_id"] == "plan-test"
        assert result["persistent_state"]["completed_results"]["step-1"] == "Done"


class TestGraphBuilder:
    """Tests for graph builder."""

    def test_build_goal_executor_creates_graph(self):
        """Test that build_goal_executor creates a valid graph."""
        graph = build_goal_executor()
        assert graph is not None
        # Graph should have nodes
        assert hasattr(graph, "nodes")

    def test_build_goal_executor_with_custom_tools(self):
        """Test building graph with custom tools."""
        from langchain_core.tools import tool

        @tool
        def custom_tool(query: str) -> str:
            """Custom tool."""
            return f"Result: {query}"

        graph = build_goal_executor(
            tools=[custom_tool],
            system_prompt="Custom system prompt",
        )
        assert graph is not None


class TestIntegration:
    """Integration tests for goal executor."""

    @pytest.mark.asyncio
    async def test_prospect_research_builds_with_goal_executor(self):
        """Test that prospect_research agent builds correctly."""
        from agents.prospect_research.prospect_research_agent import prospect_research

        graph = prospect_research()
        assert graph is not None
        assert hasattr(graph, "nodes")

"""Evals for goal executor planner.

Tests that the planner creates high-quality, actionable plans.

Run with: pytest tests/evals/goal_executor/test_planner_evals.py -v
Requires: OPENAI_API_KEY environment variable
"""

import os

import pytest
from langchain_core.messages import HumanMessage


def _has_real_api_key() -> bool:
    """Check if a real OpenAI API key is available (not a test placeholder)."""
    key = os.getenv("OPENAI_API_KEY", "")
    # Real keys start with sk- and are 40+ chars, test keys contain "test"
    return key.startswith("sk-") and len(key) >= 40 and "test" not in key.lower()


# Skip all tests if no real API key
pytestmark = pytest.mark.skipif(
    not _has_real_api_key(),
    reason="Real OPENAI_API_KEY required for evals (not test placeholder)",
)


class TestPlannerQuality:
    """Evaluate planner output quality."""

    @pytest.fixture
    def planner_state(self):
        """Create base state for planner."""
        from agents.goal_executor.state import GoalExecutorState, GoalStatus

        return GoalExecutorState(
            goal="",
            messages=[],
            status=GoalStatus.PLANNING,
            plan=None,
            current_step_id=None,
            completed_results={},
            iteration_count=0,
            max_iterations=10,
            max_parallel=1,
            final_outcome=None,
            error_message=None,
            persistent_state={},
        )

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_prospect_goal_creates_research_steps(self, planner_state):
        """Eval: Prospect research goal should create research-oriented steps."""
        from agents.goal_executor.nodes.planner import create_plan

        planner_state["goal"] = (
            "Find 3 AI infrastructure companies that recently raised Series B funding"
        )
        planner_state["messages"] = [HumanMessage(content=planner_state["goal"])]

        result = await create_plan(planner_state)
        plan = result.get("plan")

        # Assertions
        assert plan is not None, "Planner should create a plan"
        assert len(plan.steps) >= 3, "Plan should have at least 3 steps"

        # Check step quality
        step_prompts = " ".join([s.prompt.lower() for s in plan.steps])

        # Should have research-related steps
        assert any(
            word in step_prompts for word in ["search", "find", "research", "identify"]
        ), "Plan should include search/research steps"

        # Should mention funding or series B
        assert any(
            word in step_prompts
            for word in ["funding", "series", "raised", "investment"]
        ), "Plan should reference funding criteria"

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_plan_has_logical_dependencies(self, planner_state):
        """Eval: Plan steps should have logical dependencies."""
        from agents.goal_executor.nodes.planner import create_plan

        planner_state["goal"] = (
            "Research TechCorp's DevOps practices and qualify them as a prospect"
        )
        planner_state["messages"] = [HumanMessage(content=planner_state["goal"])]

        result = await create_plan(planner_state)
        plan = result.get("plan")

        assert plan is not None

        # Check that later steps depend on earlier ones
        has_dependencies = any(len(s.depends_on) > 0 for s in plan.steps)
        assert has_dependencies, "Some steps should have dependencies"

        # Verify dependencies reference valid step IDs
        step_ids = {s.id for s in plan.steps}
        for step in plan.steps:
            for dep in step.depends_on:
                assert dep in step_ids, f"Dependency {dep} should be a valid step ID"

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_plan_handles_vague_goal(self, planner_state):
        """Eval: Planner should handle vague goals gracefully."""
        from agents.goal_executor.nodes.planner import create_plan

        planner_state["goal"] = "Find some good prospects"
        planner_state["messages"] = [HumanMessage(content=planner_state["goal"])]

        result = await create_plan(planner_state)
        plan = result.get("plan")

        # Should still create a plan (with reasonable defaults)
        assert plan is not None, "Planner should handle vague goals"
        assert len(plan.steps) >= 1, "Should have at least one step"

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_plan_respects_quantity(self, planner_state):
        """Eval: Plan should respect quantity in goal."""
        from agents.goal_executor.nodes.planner import create_plan

        planner_state["goal"] = "Find exactly 5 DevOps companies in the Seattle area"
        planner_state["messages"] = [HumanMessage(content=planner_state["goal"])]

        result = await create_plan(planner_state)
        plan = result.get("plan")

        assert plan is not None

        # Plan should reference the quantity
        step_prompts = " ".join([s.prompt.lower() for s in plan.steps])
        assert "5" in step_prompts or "five" in step_prompts, (
            "Plan should mention target quantity"
        )


class TestPlannerWithContext:
    """Evaluate planner behavior with persistent state context."""

    @pytest.fixture
    def planner_state_with_history(self):
        """Create state with previous run context."""
        from agents.goal_executor.state import GoalExecutorState, GoalStatus

        return GoalExecutorState(
            goal="",
            messages=[],
            status=GoalStatus.PLANNING,
            plan=None,
            current_step_id=None,
            completed_results={},
            iteration_count=0,
            max_iterations=10,
            max_parallel=1,
            final_outcome=None,
            error_message=None,
            persistent_state={
                "previous_runs": [
                    {
                        "outcome": "Found 2 AI companies: Acme AI, TechBot",
                        "steps_completed": 4,
                    }
                ],
                "completed_results": {
                    "step_1": "Searched for AI companies, found Acme AI and TechBot",
                },
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_plan_leverages_previous_context(self, planner_state_with_history):
        """Eval: Planner should leverage previous run context."""
        from agents.goal_executor.nodes.planner import create_plan

        planner_state_with_history["goal"] = (
            "Continue finding AI companies, need 3 more"
        )
        planner_state_with_history["messages"] = [
            HumanMessage(content=planner_state_with_history["goal"])
        ]

        result = await create_plan(planner_state_with_history)
        plan = result.get("plan")

        assert plan is not None

        # Should reference continuation or additional
        step_prompts = " ".join([s.prompt.lower() for s in plan.steps])
        assert any(
            word in step_prompts
            for word in ["more", "additional", "continue", "3", "three"]
        ), "Plan should reference continuation/quantity"


class TestPlannerEdgeCases:
    """Evaluate planner handling of edge cases."""

    @pytest.fixture
    def base_state(self):
        """Create base state."""
        from agents.goal_executor.state import GoalExecutorState, GoalStatus

        return GoalExecutorState(
            goal="",
            messages=[],
            status=GoalStatus.PLANNING,
            plan=None,
            current_step_id=None,
            completed_results={},
            iteration_count=0,
            max_iterations=10,
            max_parallel=1,
            final_outcome=None,
            error_message=None,
            persistent_state={},
        )

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_handles_complex_multi_part_goal(self, base_state):
        """Eval: Handle complex goals with multiple requirements."""
        from agents.goal_executor.nodes.planner import create_plan

        base_state["goal"] = (
            "Find 3 AI companies that: 1) raised Series B+ funding in the last 6 months, "
            "2) are based in the US, 3) have DevOps or infrastructure products, "
            "and 4) have between 50-200 employees"
        )
        base_state["messages"] = [HumanMessage(content=base_state["goal"])]

        result = await create_plan(base_state)
        plan = result.get("plan")

        assert plan is not None
        # Complex goal should result in more steps
        assert len(plan.steps) >= 4, "Complex goal should have multiple steps"

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_handles_negative_constraints(self, base_state):
        """Eval: Handle goals with negative constraints."""
        from agents.goal_executor.nodes.planner import create_plan

        base_state["goal"] = (
            "Find DevOps companies that are NOT in California and have NOT raised funding yet"
        )
        base_state["messages"] = [HumanMessage(content=base_state["goal"])]

        result = await create_plan(base_state)
        plan = result.get("plan")

        assert plan is not None
        step_prompts = " ".join([s.prompt.lower() for s in plan.steps])

        # Should include exclusion criteria
        assert any(
            word in step_prompts for word in ["not", "exclude", "without", "except"]
        ), "Plan should reference exclusion criteria"

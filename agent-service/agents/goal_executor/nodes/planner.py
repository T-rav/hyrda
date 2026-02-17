"""Planner node for goal decomposition.

Uses LLM to break down a goal into executable steps with dependencies.
Follows the OpenClaw auto-planning pattern.
"""

import logging
import uuid
from datetime import UTC, datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..state import GoalExecutorState, GoalPlan, GoalStatus, GoalStep, StepStatus

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    """Schema for step in generated plan."""

    name: str = Field(..., description="Short name for the step")
    prompt: str = Field(..., description="What this step should accomplish")
    depends_on: list[str] = Field(
        default_factory=list,
        description="Names of steps that must complete before this one",
    )


class GeneratedPlan(BaseModel):
    """Schema for LLM-generated plan."""

    steps: list[PlanStep] = Field(..., description="Steps to achieve the goal")
    reasoning: str = Field("", description="Brief explanation of the approach")


PLANNER_SYSTEM_PROMPT = """You are a goal decomposition expert. Your task is to break down a goal into
concrete, executable steps.

IMPORTANT GUIDELINES:
1. Create 3-7 focused steps (not too many, not too few)
2. Each step should be independently executable
3. Order steps by dependencies - steps can only depend on earlier steps
4. Keep step prompts clear and actionable
5. Consider what tools/skills might be needed for each step

When specifying dependencies:
- Use the step NAME (not ID) in depends_on
- A step can depend on multiple prior steps
- First step(s) should have empty depends_on

For research/investigation goals:
- Start with information gathering
- Then analysis/synthesis
- Finally action or recommendation

For action/creation goals:
- Start with planning/preparation
- Then execution steps
- Finally verification/validation

Return a JSON object with the plan structure."""


async def create_plan(state: GoalExecutorState) -> dict:
    """Create execution plan from goal using LLM.

    Decomposes the goal into ordered steps with dependencies.
    Uses structured output for reliable plan extraction.

    Args:
        state: Current goal executor state with goal

    Returns:
        Updated state with plan and status
    """
    goal = state["goal"]
    persistent_state = state.get("persistent_state", {})

    logger.info(f"Creating plan for goal: {goal[:100]}...")

    # Check for existing plan in persistent state (resuming)
    if persistent_state.get("plan"):
        logger.info("Found existing plan in persistent state, resuming")
        plan_data = persistent_state["plan"]
        plan = GoalPlan(
            plan_id=plan_data["plan_id"],
            goal=plan_data["goal"],
            steps=[GoalStep(**s) for s in plan_data["steps"]],
            created_at=plan_data.get("created_at"),
            source="resume",
        )
        return {
            "plan": plan,
            "status": GoalStatus.RUNNING,
            "messages": [
                HumanMessage(content=f"Resuming goal: {goal}"),
            ],
        }

    # Create LLM with structured output (Claude Opus 4.5)
    llm = ChatAnthropic(model="claude-opus-4-5-20251101", temperature=0.3)
    structured_llm = llm.with_structured_output(GeneratedPlan)

    # Build context from persistent state if available
    context_parts = []
    if persistent_state.get("previous_runs"):
        context_parts.append(
            f"Previous run results: {persistent_state['previous_runs'][-1]}"
        )
    if persistent_state.get("learned_info"):
        context_parts.append(f"Known information: {persistent_state['learned_info']}")

    context = "\n".join(context_parts) if context_parts else ""

    # Generate plan
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""Goal: {goal}

{f"Context from previous runs:{chr(10)}{context}" if context else "This is a fresh start - no previous context."}

Create a step-by-step plan to achieve this goal. Return a JSON object with the plan."""
        ),
    ]

    try:
        generated_plan_result = await structured_llm.ainvoke(messages)
        if not isinstance(generated_plan_result, GeneratedPlan):
            # Handle dict response
            generated_plan = GeneratedPlan(**generated_plan_result)  # type: ignore[arg-type]
        else:
            generated_plan = generated_plan_result

        # Convert to GoalPlan with proper IDs
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        name_to_id: dict[str, str] = {}

        steps = []
        for i, step in enumerate(generated_plan.steps):
            step_id = f"step-{i + 1}"
            name_to_id[step.name] = step_id

            # Convert name-based dependencies to ID-based
            depends_on_ids = [
                name_to_id[dep] for dep in step.depends_on if dep in name_to_id
            ]

            steps.append(
                GoalStep(
                    id=step_id,
                    name=step.name,
                    prompt=step.prompt,
                    depends_on=depends_on_ids,
                    status=StepStatus.PENDING,
                )
            )

        plan = GoalPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            created_at=datetime.now(UTC).isoformat(),
            source="auto",
        )

        logger.info(f"Created plan {plan_id} with {len(steps)} steps")

        return {
            "plan": plan,
            "status": GoalStatus.RUNNING,
            "completed_results": {},
            "iteration_count": 0,
            "messages": [
                HumanMessage(content=f"Goal: {goal}"),
                SystemMessage(
                    content=f"Created plan with {len(steps)} steps: {generated_plan.reasoning}"
                ),
            ],
        }

    except Exception as e:
        logger.error(f"Failed to create plan: {e}", exc_info=True)
        return {
            "status": GoalStatus.FAILED,
            "error_message": f"Failed to create plan: {e}",
            "messages": [
                HumanMessage(content=f"Goal: {goal}"),
                SystemMessage(content=f"Planning failed: {e}"),
            ],
        }

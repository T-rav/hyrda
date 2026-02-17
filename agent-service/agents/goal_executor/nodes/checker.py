"""Checker node for evaluating goal progress.

Determines whether to continue execution, complete the goal, or fail.
Follows the OpenClaw pattern of plan-execute-check loops.
"""

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ..state import GoalExecutorState, GoalStatus, StepStatus

logger = logging.getLogger(__name__)


class ProgressEvaluation(BaseModel):
    """LLM evaluation of goal progress."""

    is_complete: bool = Field(..., description="Whether the goal is fully achieved")
    is_failed: bool = Field(..., description="Whether the goal cannot be achieved")
    should_continue: bool = Field(
        ..., description="Whether to continue with more steps"
    )
    summary: str = Field(..., description="Summary of current progress")
    next_action: str = Field(
        "",
        description="Suggested next action if continuing",
    )


CHECKER_SYSTEM_PROMPT = """You are a progress evaluator for goal-driven execution.

Analyze the current state and determine:
1. Is the goal COMPLETE? (all objectives achieved)
2. Has the goal FAILED? (cannot be achieved due to errors or blockers)
3. Should execution CONTINUE? (more steps needed)

Be decisive:
- If all steps succeeded and the goal is met → is_complete=true
- If critical steps failed without recovery → is_failed=true
- If there are pending steps or more work needed → should_continue=true

Consider:
- What was the original goal?
- What steps have been completed?
- What were the results?
- Are there any failures that block progress?"""


async def check_progress(state: GoalExecutorState) -> dict:
    """Evaluate progress toward the goal.

    Analyzes completed steps and determines next action:
    - Complete: Goal achieved, set final outcome
    - Failed: Goal cannot be achieved, set error
    - Continue: More work needed, continue execution loop

    Args:
        state: Current goal executor state

    Returns:
        Updated state with evaluation results
    """
    plan = state.get("plan")
    if not plan:
        return {
            "status": GoalStatus.FAILED,
            "error_message": "No plan available",
        }

    completed_results = state.get("completed_results", {})
    iteration_count = state.get("iteration_count", 0) + 1
    max_iterations = state.get("max_iterations", 10)

    # Check max iterations
    if iteration_count >= max_iterations:
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return {
            "status": GoalStatus.FAILED,
            "error_message": f"Max iterations ({max_iterations}) reached without completing goal",
            "iteration_count": iteration_count,
        }

    # Calculate step statistics
    total_steps = len(plan.steps)
    succeeded = sum(1 for s in plan.steps if s.status == StepStatus.SUCCEEDED)
    failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
    pending = sum(1 for s in plan.steps if s.status == StepStatus.PENDING)
    running = sum(1 for s in plan.steps if s.status == StepStatus.RUNNING)

    logger.info(
        f"Progress check: {succeeded}/{total_steps} succeeded, "
        f"{failed} failed, {pending} pending, {running} running"
    )

    # Quick checks before LLM
    if succeeded == total_steps:
        # All steps succeeded - goal likely complete
        summary = "\n".join(
            f"- {s.name}: {completed_results.get(s.id, 'Done')[:200]}"
            for s in plan.steps
        )
        return {
            "status": GoalStatus.COMPLETED,
            "final_outcome": f"Goal achieved with {total_steps} steps completed.\n\n{summary}",
            "iteration_count": iteration_count,
            "messages": [
                AIMessage(content=f"Goal completed: {total_steps} steps succeeded"),
            ],
        }

    if failed > 0 and pending == 0 and running == 0:
        # All remaining steps failed or skipped
        failed_steps = [s for s in plan.steps if s.status == StepStatus.FAILED]
        errors = "\n".join(f"- {s.name}: {s.error}" for s in failed_steps)
        return {
            "status": GoalStatus.FAILED,
            "error_message": f"Goal failed with {failed} step errors:\n{errors}",
            "iteration_count": iteration_count,
            "messages": [
                AIMessage(content=f"Goal failed: {failed} steps failed"),
            ],
        }

    # Use LLM for nuanced evaluation
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(ProgressEvaluation)

    # Build progress summary
    step_summaries = []
    for step in plan.steps:
        status_emoji = {
            StepStatus.SUCCEEDED: "✓",
            StepStatus.FAILED: "✗",
            StepStatus.PENDING: "○",
            StepStatus.RUNNING: "►",
            StepStatus.SKIPPED: "−",
        }.get(step.status, "?")

        result_preview = ""
        if step.id in completed_results:
            result_preview = f": {completed_results[step.id][:150]}..."
        elif step.error:
            result_preview = f": ERROR - {step.error}"

        step_summaries.append(f"[{status_emoji}] {step.name}{result_preview}")

    try:
        evaluation_result = await structured_llm.ainvoke(
            [
                SystemMessage(content=CHECKER_SYSTEM_PROMPT),
                SystemMessage(
                    content=f"""Goal: {plan.goal}

Steps Progress:
{chr(10).join(step_summaries)}

Statistics: {succeeded}/{total_steps} succeeded, {failed} failed, {pending} pending
Iteration: {iteration_count}/{max_iterations}

Evaluate the progress and determine next action."""
                ),
            ]
        )

        if not isinstance(evaluation_result, ProgressEvaluation):
            evaluation = ProgressEvaluation(**evaluation_result)  # type: ignore[arg-type]
        else:
            evaluation = evaluation_result

        if evaluation.is_complete:
            return {
                "status": GoalStatus.COMPLETED,
                "final_outcome": evaluation.summary,
                "iteration_count": iteration_count,
                "messages": [
                    AIMessage(content=f"Goal completed: {evaluation.summary}"),
                ],
            }

        if evaluation.is_failed:
            return {
                "status": GoalStatus.FAILED,
                "error_message": evaluation.summary,
                "iteration_count": iteration_count,
                "messages": [
                    AIMessage(content=f"Goal failed: {evaluation.summary}"),
                ],
            }

        # Continue execution
        return {
            "iteration_count": iteration_count,
            "messages": [
                AIMessage(
                    content=f"Progress: {evaluation.summary}. Next: {evaluation.next_action}"
                ),
            ],
        }

    except Exception as e:
        logger.error(f"Progress evaluation failed: {e}", exc_info=True)
        # Default to continuing if evaluation fails
        return {
            "iteration_count": iteration_count,
            "messages": [
                AIMessage(content=f"Continuing execution (evaluation error: {e})"),
            ],
        }


def check_router(state: GoalExecutorState) -> str:
    """Route based on check results.

    Determines next node based on goal status:
    - COMPLETED/FAILED: End execution
    - RUNNING: Continue to executor

    Args:
        state: Current state after check

    Returns:
        Next node name: "execute" or "end"
    """
    status = state.get("status", GoalStatus.RUNNING)

    if status in (GoalStatus.COMPLETED, GoalStatus.FAILED):
        return "end"

    # Check if there are more steps to execute
    plan = state.get("plan")
    if plan:
        pending = sum(1 for s in plan.steps if s.status == StepStatus.PENDING)
        if pending == 0:
            return "end"

    return "execute"

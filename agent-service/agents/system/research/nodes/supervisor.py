"""Supervisor node for parallel research coordination.

Supervisor delegates research tasks to parallel researchers and coordinates execution.
"""

import asyncio
import logging
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END
from langgraph.types import Command

from config.settings import Settings

from ..state import (
    ConductResearch,
    ResearchComplete,
    SupervisorState,
)

logger = logging.getLogger(__name__)


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[str]:
    """Supervisor node - delegates research tasks to parallel researchers.

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Command to proceed to supervisor_tools or END
    """
    research_iterations = state.get("research_iterations", 0)
    research_plan = state.get("research_plan", "")
    research_tasks = state.get("research_tasks", [])
    completed_tasks = state.get("completed_tasks", [])

    # Validate research_plan exists
    if not research_plan:
        logger.error("research_plan is missing or empty in supervisor state")
        return Command(
            goto=END,
            update={},
        )

    logger.info(f"Supervisor iteration {research_iterations}, {len(completed_tasks)}/{len(research_tasks)} tasks complete")

    # Safety limits to prevent infinite loops
    MAX_ITERATIONS = 30  # Hard limit to prevent runaway execution
    HIGH_PRIORITY_THRESHOLD = 0.8  # If 80% of HIGH tasks done, can complete

    # Check iteration limit
    if research_iterations >= MAX_ITERATIONS:
        logger.warning(f"Reached maximum iterations ({MAX_ITERATIONS}), forcing completion")
        return Command(
            goto=END,
            update={"supervisor_messages": state.get("supervisor_messages", [])},
        )

    # Auto-complete if sufficient research done
    high_priority_tasks = [t for t in research_tasks if t.priority == "HIGH"]
    high_priority_completed = [t for t in completed_tasks if t.priority == "HIGH"]

    if high_priority_tasks:
        completion_rate = len(high_priority_completed) / len(high_priority_tasks)
        if completion_rate >= HIGH_PRIORITY_THRESHOLD and len(completed_tasks) >= 10:
            logger.info(f"Auto-completing: {completion_rate:.0%} of HIGH priority tasks done, {len(completed_tasks)} total completed")
            return Command(
                goto=END,
                update={"supervisor_messages": state.get("supervisor_messages", [])},
            )

    # Check if all pending tasks are done
    pending_tasks = [t for t in research_tasks if t.status == "pending"]
    if not pending_tasks and research_iterations > 0:
        logger.info("All tasks completed, ending supervision")
        return Command(
            goto=END,
            update={"supervisor_messages": state.get("supervisor_messages", [])},
        )

    # Get LLM configuration (Settings() in thread to avoid blocking os.getcwd)
    settings = await asyncio.to_thread(lambda: Settings())

    # Create ChatOpenAI instance
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.7,
    )

    # Build supervisor prompt
    current_date = datetime.now().strftime("%B %d, %Y")

    # Format task status
    pending_tasks = [t for t in research_tasks if t.status == "pending"]
    in_progress_tasks = [t for t in research_tasks if t.status == "in_progress"]

    task_status = f"""
**Research Plan:**
{research_plan}

**Task Status:**
- Total tasks: {len(research_tasks)}
- Completed: {len(completed_tasks)}
- In progress: {len(in_progress_tasks)}
- Pending: {len(pending_tasks)}

**Available for Delegation:**
{chr(10).join([f"- [{t.task_id}] {t.description} (Priority: {t.priority})" for t in pending_tasks[:10]])}

**Completed Tasks:**
{chr(10).join([f"- [{t.task_id}] {t.description}" for t in completed_tasks[-5:]])}
"""

    system_prompt = f"""You are the Research Supervisor coordinating parallel research efforts.

Current date: {current_date}

{task_status}

**Your Role:**
1. **Delegate research** - Use ConductResearch tool to assign pending tasks to researchers
2. **Coordinate parallel execution** - You can delegate multiple tasks simultaneously (up to 3 concurrent)
3. **Monitor progress** - Check task completion and adjust strategy
4. **Complete when done** - Use ResearchComplete when all critical tasks are finished

**Delegation Strategy:**
- Prioritize HIGH priority tasks first
- **Use task_id from the Available for Delegation list**
- Provide clear, specific research questions
- Include relevant context from completed tasks
- You can delegate multiple tasks in parallel (up to 3)

**Tools:**
- ConductResearch(task_id, research_question, context) - Delegate a specific task by ID to a researcher
- ResearchComplete(summary) - Signal all critical research is complete

**When to Complete:**
- All HIGH priority tasks are done
- Most MEDIUM priority tasks are done
- Sufficient information gathered for comprehensive report

Iteration {research_iterations} - Continue delegating or complete research."""

    # Prepare messages
    messages = list(state.get("supervisor_messages", []))
    if not messages:
        messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content="Begin research coordination. Delegate tasks to researchers or complete if done."))

    # Define tools for supervisor
    tools = [ConductResearch, ResearchComplete]

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Call LLM with tools
    try:
        # Invoke LLM with tools
        response = await llm_with_tools.ainvoke(messages)

        # Check if response contains tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            # Add AI message to history
            messages.append(response)

            return Command(
                goto="supervisor_tools",
                update={
                    "supervisor_messages": messages,
                    "research_iterations": research_iterations + 1,
                },
            )
        else:
            # No tool calls, end supervision
            messages.append(response)

            return Command(
                goto=END,
                update={"supervisor_messages": messages},
            )

    except Exception as e:
        logger.error(f"Supervisor error: {e}")
        return Command(goto=END, update={})


async def supervisor_tools(
    state: SupervisorState, config: RunnableConfig
) -> Command[str]:
    """Execute supervisor tools - primarily ConductResearch delegation.

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Command to loop back to supervisor or END
    """
    messages = list(state.get("supervisor_messages", []))
    last_message = messages[-1] if messages else None

    if not last_message or not hasattr(last_message, "tool_calls"):
        logger.error("No tool calls found in supervisor_tools")
        return Command(goto=END, update={})

    # Import researcher subgraph
    from .graph_builder import build_researcher_subgraph

    researcher_subgraph = build_researcher_subgraph()

    # Process each tool call
    tool_results = []
    raw_findings = list(state.get("raw_findings", []))
    research_tasks = list(state.get("research_tasks", []))
    completed_tasks = list(state.get("completed_tasks", []))

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})

        if tool_name == "ConductResearch":
            # Delegate research to a researcher
            task_id = tool_args.get("task_id", "")
            research_question = tool_args.get("research_question", "")

            logger.info(f"Delegating task {task_id}: {research_question[:100]}")

            # Find task by exact task_id from TODO list
            matching_task = None
            for task in research_tasks:
                if task.task_id == task_id and task.status == "pending":
                    matching_task = task
                    break

            if not matching_task:
                logger.error(f"Task {task_id} not found or not pending. Available tasks: {[t.task_id for t in research_tasks if t.status == 'pending']}")
                tool_results.append(
                    ToolMessage(
                        content=f"❌ Task {task_id} not found in pending tasks",
                        tool_call_id=tool_call.get("id", ""),
                    )
                )
                continue

            try:
                # Use actual task from TODO list (ResearchTask object)
                current_task = matching_task
                logger.info(f"✅ Found TODO task {task_id}: {current_task.description}")

                # Mark task as in_progress (modify Pydantic object)
                current_task.status = "in_progress"

                # Invoke researcher subgraph
                researcher_input = {
                    "researcher_messages": [],
                    "current_task": current_task,
                    "tool_call_iterations": 0,
                    "findings": "",
                    "cached_files": [],
                    "raw_data": [],
                }

                result = await researcher_subgraph.ainvoke(researcher_input, config)

                findings = result.get("findings", "No findings")
                raw_findings.append(findings)

                # Mark task as complete in TODO list
                if matching_task:
                    matching_task.status = "completed"
                    matching_task.findings = findings
                    matching_task.completed_at = datetime.now().isoformat()
                    completed_tasks.append(matching_task)
                    logger.info(f"✅ Task {task_id} completed and added to completed_tasks")

                tool_results.append(
                    ToolMessage(
                        content=f"✅ Task {task_id} completed: {findings[:200]}...",
                        tool_call_id=tool_call.get("id", ""),
                    )
                )
            except Exception as e:
                logger.error(f"Research delegation error: {e}")
                tool_results.append(
                    ToolMessage(
                        content=f"❌ Research failed: {str(e)}",
                        tool_call_id=tool_call.get("id", ""),
                    )
                )

        elif tool_name == "ResearchComplete":
            # Supervisor signals completion
            summary = tool_args.get("summary", "")
            logger.info(f"Research complete: {summary}")

            tool_results.append(
                ToolMessage(
                    content=f"Research supervision complete. {len(raw_findings)} research units completed.",
                    tool_call_id=tool_call.get("id", ""),
                )
            )

            # Add tool messages and end
            messages.extend(tool_results)
            return Command(
                goto=END,
                update={
                    "supervisor_messages": messages,
                    "raw_findings": raw_findings,
                },
            )

    # Add tool messages and loop back to supervisor
    messages.extend(tool_results)

    return Command(
        goto="supervisor",
        update={
            "supervisor_messages": messages,
            "raw_findings": raw_findings,
            "research_tasks": research_tasks,
            "completed_tasks": completed_tasks,
        },
    )


logger.info("Supervisor nodes loaded")

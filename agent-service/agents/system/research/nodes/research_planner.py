"""Research planning node - creates structured research plan with TODO tasks."""

import os
import json
import logging

from config.settings import Settings
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI


from ..state import ResearchAgentState, ResearchTask

logger = logging.getLogger(__name__)


async def create_research_plan(state: ResearchAgentState) -> dict[str, Any]:
    """Create comprehensive research plan and break into TODO tasks.

    This node analyzes the user query and creates:
    1. High-level research strategy
    2. Specific research tasks with priorities and dependencies
    3. Report structure outline

    Args:
        state: Current research agent state

    Returns:
        Updated state with research_plan and research_tasks
    """
    query = state["query"]
    research_depth = state.get("research_depth", "standard")

    logger.info(f"Creating research plan for query: {query[:100]}...")

    # Initialize LLM with Settings (Settings() in thread to avoid blocking os.getcwd)
    # Use os.getenv to avoid blocking I/O

    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.1
    )

    # Create planning prompt
    planning_prompt = f"""You are a world-class research strategist. Create a comprehensive research plan for this query:

**Query:** {query}

**Research Depth:** {research_depth}

Create a structured research plan with:

1. **Research Strategy** (2-3 paragraphs)
   - Overall approach and methodology
   - Key information sources to target
   - Expected challenges and how to address them

2. **Research Tasks** (15-20 specific tasks for deep, comprehensive coverage)
   For each task provide:
   - Clear, specific description of what to research
   - Priority (high/medium/low)
   - Dependencies (which tasks must complete first)
   - Expected information sources

3. **Report Structure** (outline with sections)
   - Main sections the final report should have
   - Key points each section should cover

Format as JSON with keys: strategy, tasks (list of objects), report_structure

Example task format:
{{
  "description": "Research company's Q4 2023 financial performance",
  "priority": "high",
  "dependencies": []
}}
"""

    try:
        # Generate research plan
        response = await llm.ainvoke(
            [HumanMessage(content=planning_prompt)]
        )

        # Parse response (assume JSON or extract structured data)
        content = response.content

        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            plan_data = json.loads(json_match.group())
        else:
            # Fallback: treat as plain text
            plan_data = {
                "strategy": content[:500],
                "tasks": [],
                "report_structure": "Executive Summary, Key Findings, Detailed Analysis, Conclusion"
            }

        # Extract strategy
        research_plan = plan_data.get("strategy", "No strategy provided")

        # Create ResearchTask objects
        research_tasks = []
        for i, task_data in enumerate(plan_data.get("tasks", [])[:20]):  # Max 20 tasks
            task = ResearchTask(
                task_id=f"task_{i+1}",
                description=task_data.get("description", "Research task"),
                priority=task_data.get("priority", "medium"),
                status="pending",
                dependencies=task_data.get("dependencies", []),
                findings=None,
                created_at="",  # Will be set by TODO manager
                completed_at=None,
            )
            research_tasks.append(task)

        # Extract report structure
        report_structure = plan_data.get("report_structure", "")

        logger.info(f"Created research plan with {len(research_tasks)} tasks")

        return {
            "research_plan": research_plan,
            "research_tasks": research_tasks,
            "completed_tasks": [],
            "report_structure": report_structure,
            "messages": [
                AIMessage(
                    content=f"✅ Research plan created with {len(research_tasks)} tasks"
                )
            ],
        }

    except Exception as e:
        logger.error(f"Error creating research plan: {e}")
        return {
            "research_plan": f"Error creating plan: {str(e)}",
            "research_tasks": [],
            "completed_tasks": [],
            "messages": [
                AIMessage(content=f"❌ Error creating research plan: {str(e)}")
            ],
        }

"""Quality control node - validates report quality with revision loop."""

import os
import logging

from config.settings import Settings
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI


from ..configuration import (
    MAX_REVISIONS,
    MIN_FINDINGS_COUNT,
    MIN_REPORT_LENGTH,
)
from ..state import ResearchAgentState

logger = logging.getLogger(__name__)


async def quality_control(state: ResearchAgentState) -> dict[str, Any]:
    """Validate report quality and provide revision feedback.

    Checks:
    - Report length and completeness
    - Evidence and citations
    - Logical structure
    - Answers original query

    Args:
        state: Research agent state with final_report

    Returns:
        Updated state with quality flags and revision feedback
    """
    query = state["query"]
    final_report = state.get("final_report", "")
    completed_tasks = state.get("completed_tasks", [])
    revision_count = state.get("revision_count", 0)

    logger.info(f"Quality control check (revision {revision_count})")

    # Basic checks
    passes_basic = True
    issues = []

    if len(final_report) < MIN_REPORT_LENGTH:
        passes_basic = False
        issues.append(
            f"Report too short ({len(final_report)} chars, minimum {MIN_REPORT_LENGTH})"
        )

    if len(completed_tasks) < MIN_FINDINGS_COUNT:
        passes_basic = False
        issues.append(
            f"Insufficient research ({len(completed_tasks)} tasks, minimum {MIN_FINDINGS_COUNT})"
        )

    # If basic checks fail, request revision immediately
    if not passes_basic:
        logger.warning(f"Quality check failed: {', '.join(issues)}")
        return {
            "passes_quality": False,
            "revision_count": revision_count + 1,
            "revision_prompt": "\n".join(issues),
            "max_revisions_exceeded": False,
            "messages": [AIMessage(content=f"⚠️ Quality issues: {', '.join(issues)}")],
        }

    # Deep quality check with LLM
    settings = Settings()
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.1
    )

    quality_prompt = f"""Evaluate this research report for quality and completeness.

**Original Query:** {query}

**Report:**
{final_report[:3000]}...

Rate the report on:
1. **Completeness** - Does it fully answer the query?
2. **Evidence** - Is it well-supported with specific examples?
3. **Structure** - Is it logically organized and easy to follow?
4. **Depth** - Does it provide meaningful insights vs surface-level info?
5. **Accuracy** - Are claims reasonable and well-justified?

Respond with:
PASS - if report meets all criteria
REVISE - if improvements needed, followed by specific feedback

Be strict - this should be world-class research quality.
"""

    try:
        response = await llm.ainvoke([HumanMessage(content=quality_prompt)])
        evaluation = response.content

        passes = evaluation.strip().upper().startswith("PASS")

        if passes:
            logger.info("✅ Quality control passed")
            return {
                "passes_quality": True,
                "revision_count": revision_count,
                "messages": [AIMessage(content="✅ Quality control passed")],
            }
        else:
            # Extract revision feedback
            revision_feedback = evaluation.replace("REVISE", "").strip()

            # Check if max revisions exceeded
            if revision_count >= MAX_REVISIONS - 1:
                logger.warning(f"Max revisions ({MAX_REVISIONS}) exceeded")
                return {
                    "passes_quality": False,
                    "revision_count": revision_count + 1,
                    "revision_prompt": revision_feedback,
                    "max_revisions_exceeded": True,
                    "messages": [
                        AIMessage(
                            content="⚠️ Max revisions reached, accepting current report"
                        )
                    ],
                }

            logger.info("Quality check failed, requesting revision")
            return {
                "passes_quality": False,
                "revision_count": revision_count + 1,
                "revision_prompt": revision_feedback,
                "max_revisions_exceeded": False,
                "messages": [
                    AIMessage(content=f"🔄 Revision needed: {revision_feedback[:100]}...")
                ],
            }

    except Exception as e:
        logger.error(f"Error in quality control: {e}")
        # On error, accept the report
        return {
            "passes_quality": True,
            "revision_count": revision_count,
            "messages": [
                AIMessage(content=f"⚠️ Quality check error, accepting report: {str(e)}")
            ],
        }


def quality_control_router(
    state: ResearchAgentState,
) -> Literal["revise", "end"]:
    """Route based on quality control results.

    Args:
        state: Research agent state

    Returns:
        Next node: "revise" or "end"
    """
    passes_quality = state.get("passes_quality", False)
    max_revisions_exceeded = state.get("max_revisions_exceeded", False)

    if passes_quality or max_revisions_exceeded:
        return "end"
    else:
        return "revise"

"""Research brief generation node for deep research workflow.

Generates a structured research brief from user query to guide the research process.
Includes Langfuse tracing for observability.
"""

import logging
from datetime import datetime

from langchain_core.runnables import RunnableConfig

from agents.company_profile import prompts
from agents.company_profile.state import ProfileAgentState
from agents.company_profile.utils import (
    create_human_message,
    detect_profile_type,
)

logger = logging.getLogger(__name__)


async def write_research_brief(
    state: ProfileAgentState, config: RunnableConfig
) -> dict:
    """Generate research brief from user query.

    Args:
        state: Current profile agent state
        config: Runtime configuration

    Returns:
        Dict with research_brief, profile_type, and supervisor_messages
    """
    query = state["query"]

    # Clean Slack URL formatting: <http://URL|display> → display
    # This prevents LLM confusion from Slack's link format
    import re

    cleaned_query = re.sub(r"<https?://([^|>]+)\|([^>]+)>", r"\2", query)
    cleaned_query = re.sub(r"<https?://([^>]+)>", r"\1", cleaned_query)

    if cleaned_query != query:
        logger.info(f"Cleaned Slack URLs from query: '{query}' → '{cleaned_query}'")
        query = cleaned_query

    # Detect profile type if not already set
    if "profile_type" not in state or not state.get("profile_type"):
        profile_type = await detect_profile_type(query)
    else:
        profile_type = state["profile_type"]

    focus_area = state.get("focus_area", "")
    brief_revision_count = state.get("brief_revision_count", 0)
    brief_revision_prompt = state.get("brief_revision_prompt", "")

    if brief_revision_count > 0:
        logger.info(
            f"Revising research brief (attempt {brief_revision_count + 1}) for {profile_type} profile"
        )
    elif focus_area:
        logger.info(
            f"Writing research brief for {profile_type} profile with focus on: {focus_area}"
        )
    else:
        logger.info(
            f"Writing research brief for {profile_type} profile (general, no specific focus)"
        )

    # Generate research brief using LangChain ChatOpenAI with tool calling
    try:
        from langchain_openai import ChatOpenAI

        from config.settings import Settings

        settings = Settings()
        llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            temperature=0.7,
        )

        # NOTE: Don't bind internal_search_tool here - research brief is for PLANNING,
        # not EXECUTING research. Internal search should only be used by researchers
        # who have specific company names to search for.

        current_date = datetime.now().strftime("%B %d, %Y")

        # Build dynamic focus strategy and guidance
        if focus_area:
            focus_strategy = f"""**SPECIFIC FOCUS REQUESTED**: The user is specifically interested in "{focus_area}".

**Dynamic Research Approach:**
- PRIORITIZE sections directly related to: {focus_area}
- Generate 5-7 deep investigative questions for sections most relevant to {focus_area}
- For less relevant sections, generate 2-3 questions to provide necessary context
- In "Research Priorities", clearly identify which sections align with the focus area
- Connect all findings back to how they relate to {focus_area}"""

            focus_guidance = f"""
**IMPORTANT**: Since the user specifically asked about "{focus_area}", ensure your research brief:
1. Allocates 60-70% of investigative depth to sections directly related to {focus_area}
2. Still covers all 9 sections for comprehensive context (30-40% depth)
3. Explicitly calls out in "Research Priorities" which sections are most critical for {focus_area}
4. Frames questions to reveal how {focus_area} connects to BD opportunities"""
        else:
            focus_strategy = """**GENERAL PROFILE REQUEST**: No specific focus area identified.

**Balanced Research Approach:**
- Distribute research effort evenly across all 9 sections
- Generate 3-5 investigative questions per section
- Look for overall BD opportunities across all areas"""

            focus_guidance = ""

        # If this is a revision, use the revision prompt instead of the original query
        if brief_revision_prompt:
            logger.info("Using revision prompt from validation feedback")
            messages = [create_human_message(brief_revision_prompt)]
        else:
            # Select the appropriate prompt template based on profile type
            if profile_type == "employee":
                logger.info("Using employee/person-focused research brief prompt")
                prompt_template = (
                    prompts.transform_messages_into_employee_research_topic_prompt
                )
            else:  # Default to company
                prompt_template = prompts.transform_messages_into_research_topic_prompt

            # Format the selected prompt
            prompt = prompt_template.format(
                query=query,
                profile_type=profile_type,
                current_date=current_date,
                focus_area=focus_area if focus_area else "None (general profile)",
                focus_strategy=focus_strategy,
                focus_guidance=focus_guidance,
            )
            messages = [create_human_message(prompt)]

        # Execute LLM directly (no tools needed for planning)
        response = await llm.ainvoke(messages)

        research_brief = (
            response.content if hasattr(response, "content") else str(response)
        )
        logger.info(f"Research brief generated: {len(research_brief)} characters")

        # Initialize supervisor messages
        supervisor_init_msg = create_human_message(research_brief)

        return {
            "research_brief": research_brief,
            "profile_type": profile_type,
            "supervisor_messages": [supervisor_init_msg],
        }

    except Exception as e:
        logger.error(f"Research brief error: {e}", exc_info=True)

        return {
            "research_brief": f"Error generating research plan: {str(e)}",
            "final_report": f"Error generating research plan: {str(e)}",
        }

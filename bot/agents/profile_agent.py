"""Profile Agent - Company, employee, and project profile research.

Uses LangGraph deep research workflow to generate comprehensive profiles
through parallel web research and knowledge base retrieval.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from agents.base_agent import BaseAgent
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.profile_researcher import profile_researcher
from agents.company_profile.utils import detect_profile_type
from agents.registry import agent_registry

logger = logging.getLogger(__name__)


class ProfileAgent(BaseAgent):
    """Agent for company profile search and analysis using deep research.

    Handles queries like:
    - "Tell me about Tesla"
    - "Who is Elon Musk?"
    - "What is the Cybertruck project?"
    - "Show me SpaceX's profile"

    Uses hierarchical LangGraph workflow:
    - Supervisor breaks down research into parallel tasks
    - Multiple researchers gather information concurrently
    - Findings are compressed and synthesized into comprehensive report
    """

    name = "profile"
    aliases: list[str] = []
    description = "Generate comprehensive company, employee, or project profiles through deep research"

    def __init__(self):
        """Initialize ProfileAgent with deep research configuration."""
        super().__init__()
        self.config = ProfileConfiguration.from_env()
        self.graph = profile_researcher
        logger.info(
            f"ProfileAgent initialized with {self.config.search_api} search, "
            f"max {self.config.max_concurrent_research_units} concurrent researchers"
        )

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute profile research using LangGraph deep research workflow.

        Args:
            query: User query about profiles (company, employee, or project)
            context: Context dict with user_id, channel, slack_service, llm_service, etc.

        Returns:
            Result dict with comprehensive profile report and metadata
        """
        if not self.validate_context(context):
            return {
                "response": "❌ Invalid context for profile agent",
                "metadata": {"error": "missing_context"},
            }

        logger.info(f"ProfileAgent executing deep research for: {query}")

        # Get required services from context
        llm_service = context.get("llm_service")
        webcat_client = context.get("webcat_client")
        slack_service = context.get("slack_service")
        channel = context.get("channel")

        if not llm_service:
            return {
                "response": "❌ LLM service not available for profile research",
                "metadata": {"error": "no_llm_service"},
            }

        # Detect profile type
        profile_type = detect_profile_type(query)
        logger.info(f"Detected profile type: {profile_type}")

        # Send initial status message
        if slack_service and channel:
            await slack_service.send_message(
                channel=channel,
                text=f"🔍 Starting deep research for **{profile_type}** profile...\n"
                f"This may take a minute as I gather and analyze information.",
            )

        try:
            # Prepare LangGraph configuration
            graph_config = {
                "configurable": {
                    "llm_service": llm_service,
                    "webcat_client": webcat_client,
                    "search_api": self.config.search_api,
                    "max_concurrent_research_units": self.config.max_concurrent_research_units,
                    "max_researcher_iterations": self.config.max_researcher_iterations,
                    "allow_clarification": self.config.allow_clarification,
                }
            }

            # Prepare input state
            input_state = {
                "messages": [HumanMessage(content=query)],
                "query": query,
                "profile_type": profile_type,
            }

            # Execute deep research workflow
            logger.info("Invoking profile researcher graph...")
            result = await self.graph.ainvoke(input_state, graph_config)

            # Extract final report
            final_report = result.get("final_report", "")
            notes_count = len(result.get("notes", []))

            if not final_report:
                return {
                    "response": "❌ Unable to generate profile report. No research findings available.",
                    "metadata": {
                        "error": "no_report",
                        "agent": "profile",
                        "query": query,
                        "profile_type": profile_type,
                    },
                }

            logger.info(
                f"Profile research complete: {len(final_report)} chars, {notes_count} research notes"
            )

            # Format response
            response = f"# {profile_type.title()} Profile\n\n{final_report}"

            return {
                "response": response,
                "metadata": {
                    "agent": "profile",
                    "profile_type": profile_type,
                    "query": query,
                    "research_notes": notes_count,
                    "report_length": len(final_report),
                    "user_id": context.get("user_id"),
                },
            }

        except Exception as e:
            logger.error(f"ProfileAgent error: {e}", exc_info=True)
            return {
                "response": f"❌ Error during profile research: {str(e)}\n\n"
                f"Please try again or rephrase your query.",
                "metadata": {
                    "error": str(e),
                    "agent": "profile",
                    "query": query,
                    "profile_type": profile_type,
                },
            }


# Register agent with registry
agent_registry.register(
    name=ProfileAgent.name,
    agent_class=ProfileAgent,
    aliases=ProfileAgent.aliases,
)

logger.info(f"ProfileAgent registered: /{ProfileAgent.name}")

"""Profile Agent - Company, employee, and project profile research.

Uses LangGraph deep research workflow to generate comprehensive profiles
through parallel web research and knowledge base retrieval.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage

from agents.base_agent import BaseAgent
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.profile_researcher import profile_researcher
from agents.company_profile.utils import detect_profile_type
from agents.registry import agent_registry
from utils.pdf_generator import get_pdf_filename, markdown_to_pdf

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

        # Delete thinking indicator and send initial status message in the same thread
        progress_msg_ts = None
        thread_ts = context.get("thread_ts")
        if slack_service and channel:
            # Remove thinking indicator first
            thinking_ts = context.get("thinking_ts")
            if thinking_ts:
                await slack_service.delete_thinking_indicator(channel, thinking_ts)

            # Send initial progress message
            progress_response = await slack_service.send_message(
                channel=channel,
                text=f"🔍 *Deep Research Progress*\n\nStarting research for {profile_type} profile...",
                thread_ts=thread_ts,
            )
            progress_msg_ts = progress_response.get("ts") if progress_response else None

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

            # Execute deep research workflow with streaming
            logger.info("Invoking profile researcher graph with streaming...")

            # Map node names to user-friendly messages (in-progress and completed)
            node_messages = {
                "clarify_with_user": {
                    "start": "🤔 Clarifying query...",
                    "complete": "✅ Query clarified",
                },
                "write_research_brief": {
                    "start": "📝 Creating research plan...",
                    "complete": "✅ Research plan created",
                },
                "research_supervisor": {
                    "start": "🔬 Conducting parallel research...",
                    "complete": "✅ Research complete",
                },
                "final_report_generation": {
                    "start": "📊 Generating final report...",
                    "complete": "✅ Report generated",
                },
            }

            # Track completed steps
            # LangGraph events fire AFTER nodes complete, so we track what's done
            completed_steps = []
            node_order = [
                "clarify_with_user",
                "write_research_brief",
                "research_supervisor",
                "final_report_generation",
            ]

            # Show first node as starting immediately
            first_node_started = False

            result = None
            async for event in self.graph.astream(input_state, graph_config):
                logger.debug(f"Graph event: {event}")

                # Show first node starting on first event
                if (
                    not first_node_started
                    and slack_service
                    and channel
                    and progress_msg_ts
                ):
                    first_node_started = True
                    await slack_service.update_message(
                        channel=channel,
                        ts=progress_msg_ts,
                        text=f"🔍 *Deep Research Progress*\n\n{node_messages[node_order[0]]['start']}",
                    )

                # Extract node name from event
                if isinstance(event, dict):
                    for node_name, _ in event.items():
                        if node_name in node_messages:
                            # This node just completed
                            completed_steps.append(node_messages[node_name]["complete"])
                            logger.info(f"Completed node: {node_name}")

                            # Show next in-progress step if available
                            if slack_service and channel and progress_msg_ts:
                                # Find next step to show as in-progress
                                all_steps = list(completed_steps)

                                # Add next step as in-progress if there is one
                                try:
                                    current_index = node_order.index(node_name)
                                    if current_index + 1 < len(node_order):
                                        next_node = node_order[current_index + 1]
                                        all_steps.append(
                                            node_messages[next_node]["start"]
                                        )
                                except (ValueError, IndexError):
                                    pass

                                steps_text = "\n".join(all_steps)
                                await slack_service.update_message(
                                    channel=channel,
                                    ts=progress_msg_ts,
                                    text=f"🔍 *Deep Research Progress*\n\n{steps_text}",
                                )

                # Store final result
                result = event

            # Get the final state from the last event
            if result and isinstance(result, dict):
                # LangGraph returns the final state in the last event
                result = list(result.values())[0] if result else {}

            # Extract final report and executive summary
            final_report = result.get("final_report", "")
            executive_summary = result.get("executive_summary", "")
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

            # Generate PDF from full report
            pdf_title = f"{profile_type.title()} Profile"
            pdf_metadata = {
                "Query": query,
                "Profile Type": profile_type.title(),
                "Research Notes": str(notes_count),
                "Generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            pdf_bytes = markdown_to_pdf(
                markdown_content=final_report,
                title=pdf_title,
                metadata=pdf_metadata,
                style=self.config.pdf_style,
            )

            # Upload PDF to Slack if available
            pdf_uploaded = False
            if slack_service and channel:
                try:
                    pdf_filename = get_pdf_filename(
                        title=f"{profile_type.title()} Profile - {query[:30]}",
                        profile_type=profile_type,
                    )

                    upload_response = await slack_service.upload_file(
                        channel=channel,
                        file_content=pdf_bytes,
                        filename=pdf_filename,
                        title=pdf_title,
                        initial_comment=None,  # Summary sent separately
                        thread_ts=context.get("thread_ts"),
                    )

                    if upload_response:
                        pdf_uploaded = True
                        logger.info(f"PDF report uploaded: {pdf_filename}")
                    else:
                        logger.warning("Failed to upload PDF to Slack")

                except Exception as pdf_error:
                    logger.error(f"Error uploading PDF: {pdf_error}")

            # Use executive summary if available and PDF uploaded, otherwise full report
            if executive_summary and pdf_uploaded:
                response = executive_summary
                logger.info("Sending executive summary (PDF attached)")
            else:
                # Fallback to full markdown report (without profile type header)
                response = final_report
                logger.info("Sending full markdown report (no PDF)")

            return {
                "response": response,
                "metadata": {
                    "agent": "profile",
                    "profile_type": profile_type,
                    "query": query,
                    "research_notes": notes_count,
                    "report_length": len(final_report),
                    "pdf_generated": pdf_bytes is not None,
                    "pdf_uploaded": pdf_uploaded,
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

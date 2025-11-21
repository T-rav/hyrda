"""Profile Agent - Company, employee, and project profile research.

Uses LangGraph deep research workflow to generate comprehensive profiles
through parallel web research and knowledge base retrieval.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agents.base_agent import BaseAgent
from agents.profiler.configuration import ProfileConfiguration
from agents.profiler.nodes.graph_builder import build_profile_researcher
from agents.profiler.utils import detect_profile_type, extract_focus_area
from agents.registry import agent_registry
from utils.pdf_generator import get_pdf_filename, markdown_to_pdf

logger = logging.getLogger(__name__)

# Singleton checkpointer shared across all ProfileAgent instances
_checkpointer = None

# Module-level graph variable for testing (mocked by tests)
# This is set during ProfileAgent initialization
profile_researcher = None


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Examples:
        5.2 -> "5.2s"
        65.0 -> "1m 5s"
        3661.5 -> "1h 1m 2s"

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


class ProfileAgent(BaseAgent):
    """Agent for company profile search and analysis using deep research.

    Handles queries like:
    - "Tell me about Tesla"
    - "Tell me about Tesla's AI needs"
    - "What is Stripe's payment infrastructure?"
    - "Show me SpaceX's profile"

    Uses hierarchical LangGraph workflow:
    - Supervisor breaks down research into parallel tasks
    - Multiple researchers gather information concurrently
    - Findings are compressed and synthesized into comprehensive report
    """

    name = "profile"
    aliases: list[str] = ["-profile"]
    description = "Generate comprehensive company profiles through deep research (supports specific focus areas like 'AI needs', 'DevOps practices', etc.)"

    def __init__(self):
        """Initialize ProfileAgent with deep research configuration."""
        super().__init__()
        self.config = ProfileConfiguration.from_env()

        # Initialize singleton checkpointer and graph
        self._ensure_graph_initialized()
        logger.info(
            f"ProfileAgent initialized with {self.config.search_api} search, "
            f"max {self.config.max_concurrent_research_units} concurrent researchers"
        )

    def _ensure_graph_initialized(self):
        """Ensure singleton checkpointer and graph are initialized."""
        global _checkpointer, profile_researcher  # noqa: PLW0603

        # Check if profile_researcher is already set (by tests mocking it)
        if profile_researcher is not None:
            # Tests have mocked the graph, use the mock
            self.graph = profile_researcher
            logger.info("✅ Using mocked profile_researcher graph from tests")
            return

        if _checkpointer is None:
            # Create singleton MemorySaver - shared across all agent instances
            _checkpointer = MemorySaver()
            logger.info("✅ Initialized singleton MemorySaver checkpointer")

        # Build graph with checkpointer
        self.graph = build_profile_researcher(checkpointer=_checkpointer)

        # Set module-level variable for test mocking compatibility
        profile_researcher = self.graph

        logger.info("✅ Built profile researcher graph with singleton checkpointer")

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute profile research using LangGraph deep research workflow.

        Args:
            query: User query about company profiles (optionally with specific focus area)
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
        slack_service = context.get("slack_service")
        channel = context.get("channel")

        if not llm_service:
            return {
                "response": "❌ LLM service not available for profile research",
                "metadata": {"error": "no_llm_service"},
            }

        # Detect profile type and extract focus area
        profile_type = await detect_profile_type(query, llm_service)
        focus_area = await extract_focus_area(query, llm_service)

        if focus_area:
            logger.info(
                f"Detected profile type: {profile_type}, Focus area: {focus_area}"
            )
        else:
            logger.info(
                f"Detected profile type: {profile_type} (general profile, no specific focus)"
            )

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
            # Initialize internal deep research service for knowledge base searching
            from services.internal_deep_research import (
                get_internal_deep_research_service,
            )

            internal_deep_research = await get_internal_deep_research_service()
            if internal_deep_research:
                logger.info(
                    "Internal deep research service initialized for profile agent"
                )
            else:
                logger.warning(
                    "Internal deep research service not available - knowledge base searching disabled"
                )

            # Prepare LangGraph configuration
            # Use thread_ts as the LangGraph thread_id for state persistence (matches meddic_agent pattern)
            import time

            thread_id = (
                thread_ts
                if thread_ts
                else f"profile_{context.get('user_id', 'unknown')}_{int(time.time())}"
            )
            logger.info(
                f"🔗 Running profile researcher graph with thread_id: {thread_id}"
            )

            graph_config = {
                "configurable": {
                    "thread_id": thread_id,  # Required by MemorySaver checkpointer
                    "llm_service": llm_service,
                    "search_api": self.config.search_api,
                    "max_concurrent_research_units": self.config.max_concurrent_research_units,
                    "max_researcher_iterations": self.config.max_researcher_iterations,
                    "allow_clarification": self.config.allow_clarification,
                    "internal_deep_research": internal_deep_research,  # Enable knowledge base search
                }
            }

            # Prepare input state
            input_state = {
                "messages": [HumanMessage(content=query)],
                "query": query,
                "profile_type": profile_type,
                "focus_area": focus_area,
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
                "quality_control": {
                    "start": "🔍 Validating report quality...",
                    "complete": "✅ Quality check complete",
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
                "quality_control",
            ]

            # Track timing for each node
            import time

            node_start_times = {}
            node_durations = {}
            node_execution_counts = {}  # Track how many times each node executes

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
                    node_start_times[node_order[0]] = time.time()
                    await slack_service.update_message(
                        channel=channel,
                        ts=progress_msg_ts,
                        text=f"🔍 *Deep Research Progress*\n\n{node_messages[node_order[0]]['start']}",
                    )

                # Extract node name from event
                if isinstance(event, dict):
                    for node_name, node_data in event.items():
                        if node_name in node_messages:
                            # Track execution count for this node
                            node_execution_counts[node_name] = (
                                node_execution_counts.get(node_name, 0) + 1
                            )
                            execution_count = node_execution_counts[node_name]

                            # Calculate duration for this node
                            end_time = time.time()
                            start_time = node_start_times.get(node_name)
                            duration = end_time - start_time if start_time else 0
                            node_durations[node_name] = duration

                            # Check if quality control is requesting a revision
                            # by looking at revision_count in state data
                            is_quality_failure = False
                            if node_name == "quality_control" and isinstance(
                                node_data, dict
                            ):
                                revision_count = node_data.get("revision_count", 0)
                                if revision_count > 0:
                                    is_quality_failure = True
                                    logger.info(
                                        f"Quality control FAILED, revision_count={revision_count}, will loop back"
                                    )

                            # Build completion message with duration
                            duration_text = (
                                f" ({format_duration(duration)})"
                                if duration > 0
                                else ""
                            )

                            # Add revision indicator for nodes that loop
                            revision_text = ""
                            if (
                                node_name
                                in ["final_report_generation", "quality_control"]
                                and execution_count > 1
                            ):
                                revision_text = f" [Attempt {execution_count}]"

                            # Special message for quality control failures
                            complete_message = node_messages[node_name]["complete"]
                            if is_quality_failure:
                                complete_message = (
                                    "⚠️ Quality check failed - revision needed"
                                )

                            completed_steps.append(
                                f"{complete_message}{duration_text}{revision_text}"
                            )
                            logger.info(
                                f"✅ Completed node: {node_name} in {duration:.1f}s (attempt {execution_count})"
                            )

                            # Show next in-progress step if available
                            if slack_service and channel and progress_msg_ts:
                                # Find next step to show as in-progress
                                all_steps = list(completed_steps)

                                # Determine next node
                                # Special case: if quality_control failed, loop back to final_report
                                next_node = None
                                next_node_attempt = 1

                                if (
                                    node_name == "quality_control"
                                    and is_quality_failure
                                ):
                                    # Quality control failed - loop back for revision
                                    next_node = "final_report_generation"
                                    # revision_count in state is already incremented
                                    revision_count = (
                                        node_data.get("revision_count", 0)
                                        if isinstance(node_data, dict)
                                        else 0
                                    )
                                    next_node_attempt = (
                                        revision_count + 1
                                    )  # +1 because revision_count is 0-indexed
                                    logger.info(
                                        f"Quality control FAILED (revision_count={revision_count}) - will loop back to final_report for attempt {next_node_attempt}"
                                    )
                                else:
                                    # Normal forward flow - find next node in order
                                    try:
                                        current_index = node_order.index(node_name)
                                        logger.info(
                                            f"Node {node_name} at index {current_index}/{len(node_order) - 1}"
                                        )
                                        if current_index + 1 < len(node_order):
                                            next_node = node_order[current_index + 1]
                                            # Check if next node has executed before (for attempt number)
                                            next_node_attempt = (
                                                node_execution_counts.get(next_node, 0)
                                                + 1
                                            )
                                        else:
                                            logger.info("No more nodes to process")
                                    except (ValueError, IndexError) as e:
                                        logger.warning(
                                            f"Could not find node {node_name} in order: {e}"
                                        )

                                # Add next node as in-progress if we have one
                                if next_node:
                                    # Record start time for next node
                                    node_start_times[next_node] = time.time()

                                    # Build in-progress message with attempt indicator
                                    next_revision_text = ""
                                    if (
                                        next_node
                                        in [
                                            "final_report_generation",
                                            "quality_control",
                                        ]
                                        and next_node_attempt > 1
                                    ):
                                        next_revision_text = (
                                            f" [Attempt {next_node_attempt}]"
                                        )

                                    all_steps.append(
                                        f"{node_messages[next_node]['start']}{next_revision_text}"
                                    )
                                    logger.info(
                                        f"⏳ Starting next node: {next_node} - {node_messages[next_node]['start']}{next_revision_text}"
                                    )

                                steps_text = "\n".join(all_steps)
                                await slack_service.update_message(
                                    channel=channel,
                                    ts=progress_msg_ts,
                                    text=f"🔍 *Deep Research Progress*\n\n{steps_text}",
                                )
                                logger.info(
                                    f"Updated progress UI: {len(all_steps)} steps"
                                )

                # Store ALL events as result - we'll extract the final state after the loop
                # The last event from astream contains the final state
                result = event

            # Log final event structure for debugging
            if result and isinstance(result, dict):
                event_keys = list(result.keys())
                logger.info(f"Final LangGraph event keys: {event_keys}")
                # Log if it's an __end__ event or a node event
                if "__end__" in event_keys:
                    logger.info("Final event is __end__ event (quality control passed)")
                elif any(key in node_order for key in event_keys):
                    logger.info(
                        f"Final event is node event: {[k for k in event_keys if k in node_order]}"
                    )
                else:
                    logger.warning(f"Final event has unexpected keys: {event_keys}")
            else:
                logger.error(
                    f"Final event is not a dict: type={type(result)}, value={result}"
                )

            # Get the final state from LangGraph using checkpointer
            try:
                final_state_snapshot = await self.graph.aget_state(graph_config)
                if final_state_snapshot and hasattr(final_state_snapshot, "values"):
                    result = final_state_snapshot.values
                    logger.info(
                        f"✅ Retrieved final state from checkpointer: has final_report: {'final_report' in result}"
                    )
                else:
                    logger.error("Checkpointer returned invalid state snapshot")
                    result = {}
            except Exception as state_error:
                logger.error(
                    f"❌ Error retrieving final state from checkpointer: {state_error}"
                )
                result = {}

            # Ensure result is a dict
            if not isinstance(result, dict):
                logger.error(f"Invalid result type: {type(result)}, value: {result}")
                result = {}

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

            # Cache markdown report BEFORE converting to PDF (for follow-up questions)
            thread_ts = context.get("thread_ts")
            conversation_cache = context.get("conversation_cache")

            logger.info(
                f"🔍 DEBUG: Attempting to cache report - thread_ts={thread_ts}, "
                f"conversation_cache={conversation_cache is not None}"
            )

            if thread_ts and conversation_cache:
                try:
                    # Cache the full markdown report for follow-up questions
                    pdf_filename_preview = (
                        f"{profile_type.title()}_Profile_{query[:30]}.pdf"
                    )
                    await conversation_cache.store_document_content(
                        thread_ts, final_report, pdf_filename_preview
                    )
                    logger.info(f"✅ Stored document content for thread {thread_ts}")

                    # Mark this thread as a profile thread to disable RAG
                    await conversation_cache.set_thread_type(thread_ts, "profile")
                    logger.info(f"✅ Set thread_type='profile' for thread {thread_ts}")

                    logger.info(
                        f"✅ Cached markdown report and marked as profile thread {thread_ts}"
                    )
                except Exception as cache_error:
                    logger.error(
                        f"❌ Failed to cache markdown report: {cache_error}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    f"⚠️ Skipping cache - thread_ts={thread_ts}, "
                    f"conversation_cache={conversation_cache is not None}"
                )

            # Generate PDF title with entity name extracted by LLM
            try:
                import json

                from langchain_openai import ChatOpenAI

                from config.settings import Settings

                settings = Settings()

                extraction_prompt = f"""Extract the main entity name from this query and return it as a JSON object.

Query: "{query}"

Examples:
- "tell me about Tesla" → {{"entity": "Tesla"}}
- "profile of Elon Musk" → {{"entity": "Elon Musk"}}
- "what is the Cybertruck project?" → {{"entity": "Cybertruck"}}
- "SpaceX" → {{"entity": "SpaceX"}}
- "research Microsoft Azure" → {{"entity": "Microsoft Azure"}}

Return ONLY a JSON object in this format: {{"entity": "name here"}}"""

                # Use ChatOpenAI directly (same as other LangGraph nodes)
                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=settings.llm.api_key,
                    temperature=0.0,
                    max_completion_tokens=30,
                )

                entity_response = await llm.ainvoke(extraction_prompt)
                entity_text = entity_response.content.strip()

                # Parse JSON response
                entity_data = json.loads(entity_text)
                entity_name = entity_data.get("entity", "").strip()

                logger.info(
                    f"LLM returned entity name: '{entity_name}' (length: {len(entity_name)})"
                )

                if entity_name and len(entity_name) > 0 and len(entity_name) < 100:
                    # Use friendly profile type names
                    profile_label = (
                        "Professional Profile"
                        if profile_type == "employee"
                        else "Company Profile"
                    )
                    pdf_title = f"{entity_name} - {profile_label}"
                    logger.info(
                        f"✅ Using extracted entity name in PDF title: '{pdf_title}'"
                    )
                else:
                    # Fallback to generic title
                    profile_label = (
                        "Professional Profile"
                        if profile_type == "employee"
                        else "Company Profile"
                    )
                    pdf_title = profile_label
                    logger.warning(
                        f"⚠️ Entity name invalid ('{entity_name}'), using generic title: '{pdf_title}'"
                    )

            except Exception as e:
                logger.warning(
                    f"Error extracting entity name: {e}, using generic title"
                )
                profile_label = (
                    "Professional Profile"
                    if profile_type == "employee"
                    else "Company Profile"
                )
                pdf_title = profile_label

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

            # Prepare response text (executive summary or full report)
            if executive_summary:
                response_text = executive_summary
                logger.info("Using executive summary as response")
            else:
                response_text = final_report
                logger.info("Using full markdown report as response")

            # Upload PDF to Slack with summary as initial comment
            pdf_uploaded = False
            if slack_service and channel:
                try:
                    pdf_filename = get_pdf_filename(
                        title=f"{profile_type.title()} Profile - {query[:30]}",
                        profile_type=profile_type,
                    )

                    # Use executive summary as initial comment if available
                    # This ensures PDF and summary appear together (summary first, then PDF below)
                    initial_comment = executive_summary if executive_summary else None

                    upload_response = await slack_service.upload_file(
                        channel=channel,
                        file_content=pdf_bytes,
                        filename=pdf_filename,
                        title=pdf_title,
                        initial_comment=initial_comment,
                        thread_ts=context.get("thread_ts"),
                    )

                    if upload_response:
                        pdf_uploaded = True
                        logger.info(f"PDF report uploaded with summary: {pdf_filename}")
                    else:
                        logger.warning("Failed to upload PDF to Slack")

                except Exception as pdf_error:
                    logger.error(f"Error uploading PDF: {pdf_error}")

            # If PDF was uploaded, ALWAYS return empty response
            # (summary is posted as initial_comment with the PDF)
            logger.info(
                f"Decision point: executive_summary={bool(executive_summary)}, pdf_uploaded={pdf_uploaded}"
            )
            if pdf_uploaded:
                # PDF was uploaded successfully - don't post anything else to Slack
                # The summary is already attached to the PDF as initial_comment
                response = ""
                logger.info(
                    "✅ PDF uploaded with summary attached, returning EMPTY response"
                )
            else:
                # PDF upload failed - post the full report or summary as fallback
                response = response_text
                logger.info(
                    f"⚠️ PDF upload failed, returning response text as fallback ({len(response_text)} chars)"
                )

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
                    "clear_thread_tracking": True,  # Clear tracking so follow-ups use regular LLM
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

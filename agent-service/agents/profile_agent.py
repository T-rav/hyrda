"""Profile Agent - Company, employee, and project profile research.

Uses LangGraph deep research workflow to generate comprehensive profiles
through parallel web research and knowledge base retrieval.

REFACTORED VERSION: Giant run() method broken into focused helper methods.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from agents.base_agent import BaseAgent
from agents.profiler.configuration import ProfileConfiguration
from agents.profiler.nodes.graph_builder import build_profile_researcher
from agents.profiler.utils import detect_profile_type, extract_focus_area
from agents.registry import agent_registry
from config.settings import Settings
from services.internal_deep_research import get_internal_deep_research_service
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

    def _validate_and_get_services(
        self, context: dict[str, Any]
    ) -> tuple[Any, Any, str] | None:
        """Validate context and extract required services.

        Args:
            context: Agent context dictionary

        Returns:
            Tuple of (llm_service, slack_service, channel) or None if validation fails
        """
        if not self.validate_context(context):
            return None

        llm_service = context.get("llm_service")
        slack_service = context.get("slack_service")
        channel = context.get("channel")

        if not llm_service:
            return None

        return llm_service, slack_service, channel

    async def _detect_profile_info(
        self, query: str, llm_service: Any
    ) -> tuple[str, str | None]:
        """Detect profile type and extract focus area from query.

        Args:
            query: User query
            llm_service: LLM service for detection

        Returns:
            Tuple of (profile_type, focus_area)
        """
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

        return profile_type, focus_area

    async def _setup_progress_message(
        self,
        slack_service: Any,
        channel: str,
        profile_type: str,
        thread_ts: str | None,
        thinking_ts: str | None,
    ) -> str | None:
        """Setup initial progress message in Slack.

        Args:
            slack_service: Slack service
            channel: Slack channel
            profile_type: Detected profile type
            thread_ts: Thread timestamp
            thinking_ts: Thinking indicator timestamp to delete

        Returns:
            Progress message timestamp or None
        """
        if not slack_service or not channel:
            return None

        # Remove thinking indicator first
        if thinking_ts:
            await slack_service.delete_thinking_indicator(channel, thinking_ts)

        # Send initial progress message
        progress_response = await slack_service.send_message(
            channel=channel,
            text=f"🔍 *Deep Research Progress*\n\nStarting research for {profile_type} profile...",
            thread_ts=thread_ts,
        )
        return progress_response.get("ts") if progress_response else None

    async def _initialize_research_service(self) -> Any:
        """Initialize internal deep research service for knowledge base searching.

        Returns:
            Internal deep research service instance or None
        """
        internal_deep_research = await get_internal_deep_research_service()
        if internal_deep_research:
            logger.info("Internal deep research service initialized for profile agent")
        else:
            logger.warning(
                "Internal deep research service not available - knowledge base searching disabled"
            )

        return internal_deep_research

    def _prepare_graph_config(
        self,
        llm_service: Any,
        internal_deep_research: Any,
        thread_ts: str | None,
        user_id: str,
    ) -> dict[str, Any]:
        """Prepare LangGraph configuration.

        Args:
            llm_service: LLM service
            internal_deep_research: Internal research service
            thread_ts: Thread timestamp for state persistence
            user_id: User ID for fallback thread ID

        Returns:
            Graph configuration dictionary
        """
        thread_id = thread_ts if thread_ts else f"profile_{user_id}_{int(time.time())}"
        logger.info(f"🔗 Running profile researcher graph with thread_id: {thread_id}")

        return {
            "configurable": {
                "thread_id": thread_id,
                "llm_service": llm_service,
                "search_api": self.config.search_api,
                "max_concurrent_research_units": self.config.max_concurrent_research_units,
                "max_researcher_iterations": self.config.max_researcher_iterations,
                "allow_clarification": self.config.allow_clarification,
                "internal_deep_research": internal_deep_research,
            }
        }

    def _create_input_state(
        self, query: str, profile_type: str, focus_area: str | None
    ) -> dict[str, Any]:
        """Create input state for LangGraph execution.

        Args:
            query: User query
            profile_type: Detected profile type
            focus_area: Optional focus area

        Returns:
            Input state dictionary
        """
        return {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "profile_type": profile_type,
            "focus_area": focus_area,
        }

    def _get_node_messages(self) -> dict[str, dict[str, str]]:
        """Get node progress messages configuration.

        Returns:
            Dictionary mapping node names to start/complete messages
        """
        return {
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

    def _get_node_order(self) -> list[str]:
        """Get ordered list of graph nodes.

        Returns:
            List of node names in execution order
        """
        return [
            "clarify_with_user",
            "write_research_brief",
            "research_supervisor",
            "final_report_generation",
            "quality_control",
        ]

    async def _execute_graph_with_progress(
        self,
        input_state: dict[str, Any],
        graph_config: dict[str, Any],
        slack_service: Any,
        channel: str,
        progress_msg_ts: str | None,
    ) -> Any:
        """Execute LangGraph workflow with real-time progress updates.

        Args:
            input_state: Input state for graph
            graph_config: Graph configuration
            slack_service: Slack service for progress updates
            channel: Slack channel
            progress_msg_ts: Progress message timestamp

        Returns:
            Final event from graph execution
        """
        logger.info("Invoking profile researcher graph with streaming...")

        node_messages = self._get_node_messages()
        node_order = self._get_node_order()

        # Initialize tracking structures
        completed_steps = []
        node_start_times = {}
        node_durations = {}
        node_execution_counts = {}
        first_node_started = False

        result = None
        async for event in self.graph.astream(input_state, graph_config):
            logger.debug(f"Graph event: {event}")

            # Show first node starting on first event
            if not first_node_started and slack_service and channel and progress_msg_ts:
                first_node_started = True
                node_start_times[node_order[0]] = time.time()
                await slack_service.update_message(
                    channel=channel,
                    ts=progress_msg_ts,
                    text=f"🔍 *Deep Research Progress*\n\n{node_messages[node_order[0]]['start']}",
                )

            # Process node completion events
            if isinstance(event, dict):
                for node_name, node_data in event.items():
                    if node_name in node_messages:
                        await self._handle_node_completion(
                            node_name,
                            node_data,
                            node_messages,
                            node_order,
                            completed_steps,
                            node_start_times,
                            node_durations,
                            node_execution_counts,
                            slack_service,
                            channel,
                            progress_msg_ts,
                        )

            result = event

        return result

    async def _handle_node_completion(
        self,
        node_name: str,
        node_data: Any,
        node_messages: dict,
        node_order: list[str],
        completed_steps: list[str],
        node_start_times: dict,
        node_durations: dict,
        node_execution_counts: dict,
        slack_service: Any,
        channel: str,
        progress_msg_ts: str | None,
    ):
        """Handle completion of a graph node with progress update.

        Args:
            node_name: Name of completed node
            node_data: Node output data
            node_messages: Progress messages configuration
            node_order: Ordered list of nodes
            completed_steps: List of completed step messages
            node_start_times: Dictionary of node start times
            node_durations: Dictionary of node durations
            node_execution_counts: Dictionary tracking execution counts
            slack_service: Slack service
            channel: Slack channel
            progress_msg_ts: Progress message timestamp
        """
        # Track execution count
        node_execution_counts[node_name] = node_execution_counts.get(node_name, 0) + 1
        execution_count = node_execution_counts[node_name]

        # Calculate duration
        end_time = time.time()
        start_time = node_start_times.get(node_name)
        duration = end_time - start_time if start_time else 0
        node_durations[node_name] = duration

        # Check for quality control failure
        is_quality_failure = False
        if node_name == "quality_control" and isinstance(node_data, dict):
            revision_count = node_data.get("revision_count", 0)
            if revision_count > 0:
                is_quality_failure = True
                logger.info(
                    f"Quality control FAILED, revision_count={revision_count}, will loop back"
                )

        # Build completion message
        duration_text = f" ({format_duration(duration)})" if duration > 0 else ""
        revision_text = (
            f" [Attempt {execution_count}]"
            if node_name in ["final_report_generation", "quality_control"]
            and execution_count > 1
            else ""
        )

        complete_message = node_messages[node_name]["complete"]
        if is_quality_failure:
            complete_message = "⚠️ Quality check failed - revision needed"

        completed_steps.append(f"{complete_message}{duration_text}{revision_text}")
        logger.info(
            f"✅ Completed node: {node_name} in {duration:.1f}s (attempt {execution_count})"
        )

        # Update Slack progress message with next node
        if slack_service and channel and progress_msg_ts:
            next_node = self._determine_next_node(
                node_name, is_quality_failure, node_data, node_order
            )

            if next_node:
                next_node_attempt = node_execution_counts.get(next_node, 0) + 1
                node_start_times[next_node] = time.time()

                next_revision_text = (
                    f" [Attempt {next_node_attempt}]"
                    if next_node in ["final_report_generation", "quality_control"]
                    and next_node_attempt > 1
                    else ""
                )

                all_steps = list(completed_steps)
                all_steps.append(
                    f"{node_messages[next_node]['start']}{next_revision_text}"
                )

                steps_text = "\n".join(all_steps)
                await slack_service.update_message(
                    channel=channel,
                    ts=progress_msg_ts,
                    text=f"🔍 *Deep Research Progress*\n\n{steps_text}",
                )

    def _determine_next_node(
        self,
        current_node: str,
        is_quality_failure: bool,
        node_data: Any,
        node_order: list[str],
    ) -> str | None:
        """Determine next node in workflow.

        Args:
            current_node: Current node name
            is_quality_failure: Whether quality control failed
            node_data: Node output data
            node_order: Ordered list of nodes

        Returns:
            Next node name or None
        """
        if current_node == "quality_control" and is_quality_failure:
            # Loop back to final_report for revision
            return "final_report_generation"

        # Normal forward flow
        try:
            current_index = node_order.index(current_node)
            if current_index + 1 < len(node_order):
                return node_order[current_index + 1]
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not find node {current_node} in order: {e}")

        return None

    async def _extract_final_state(
        self, graph_config: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """Extract final state from LangGraph execution.

        Args:
            graph_config: Graph configuration
            result: Final event from graph execution

        Returns:
            Final state dictionary
        """
        # Log final event structure
        if result and isinstance(result, dict):
            event_keys = list(result.keys())
            logger.info(f"Final LangGraph event keys: {event_keys}")

        # Get state from checkpointer
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

        if not isinstance(result, dict):
            logger.error(f"Invalid result type: {type(result)}, value: {result}")
            result = {}

        return result

    async def _cache_report(
        self,
        final_report: str,
        profile_type: str,
        query: str,
        thread_ts: str | None,
        conversation_cache: Any,
    ):
        """Cache markdown report for follow-up questions.

        Args:
            final_report: Generated markdown report
            profile_type: Profile type
            query: User query
            thread_ts: Thread timestamp
            conversation_cache: Conversation cache service
        """
        if not thread_ts or not conversation_cache:
            logger.warning(
                f"⚠️ Skipping cache - thread_ts={thread_ts}, "
                f"conversation_cache={conversation_cache is not None}"
            )
            return

        try:
            pdf_filename_preview = f"{profile_type.title()}_Profile_{query[:30]}.pdf"
            await conversation_cache.store_document_content(
                thread_ts, final_report, pdf_filename_preview
            )
            logger.info(f"✅ Stored document content for thread {thread_ts}")

            # Mark thread as profile thread to disable RAG
            await conversation_cache.set_thread_type(thread_ts, "profile")
            logger.info(f"✅ Set thread_type='profile' for thread {thread_ts}")
        except Exception as cache_error:
            logger.error(
                f"❌ Failed to cache markdown report: {cache_error}",
                exc_info=True,
            )

    async def _generate_pdf_title(self, query: str) -> str:
        """Generate PDF title by extracting entity name from query.

        Args:
            query: User query

        Returns:
            PDF title string
        """
        try:
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

            llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.llm.api_key,
                temperature=0.0,
                max_completion_tokens=30,
            )

            entity_response = await llm.ainvoke(extraction_prompt)
            entity_text = entity_response.content.strip()
            entity_data = json.loads(entity_text)
            entity_name = entity_data.get("entity", "").strip()

            logger.info(
                f"LLM returned entity name: '{entity_name}' (length: {len(entity_name)})"
            )

            if entity_name and 0 < len(entity_name) < 100:
                pdf_title = f"{entity_name} - Profile"
                logger.info(
                    f"✅ Using extracted entity name in PDF title: '{pdf_title}'"
                )
                return pdf_title

        except Exception as e:
            logger.warning(f"Error extracting entity name: {e}, using generic title")

        return "Profile"

    async def _upload_pdf_to_slack(
        self,
        slack_service: Any,
        channel: str,
        pdf_bytes: bytes,
        pdf_title: str,
        profile_type: str,
        query: str,
        executive_summary: str | None,
        thread_ts: str | None,
    ) -> bool:
        """Upload PDF report to Slack.

        Args:
            slack_service: Slack service
            channel: Slack channel
            pdf_bytes: PDF file bytes
            pdf_title: PDF title
            profile_type: Profile type
            query: User query
            executive_summary: Optional executive summary
            thread_ts: Thread timestamp

        Returns:
            True if upload succeeded, False otherwise
        """
        if not slack_service or not channel:
            return False

        try:
            pdf_filename = get_pdf_filename(
                title=f"{profile_type.title()} Profile - {query[:30]}",
                profile_type=profile_type,
            )

            initial_comment = executive_summary if executive_summary else None

            upload_response = await slack_service.upload_file(
                channel=channel,
                file_content=pdf_bytes,
                filename=pdf_filename,
                title=pdf_title,
                initial_comment=initial_comment,
                thread_ts=thread_ts,
            )

            if upload_response:
                logger.info(f"PDF report uploaded with summary: {pdf_filename}")
                return True
            else:
                logger.warning("Failed to upload PDF to Slack")
                return False

        except Exception as pdf_error:
            logger.error(f"Error uploading PDF: {pdf_error}")
            return False

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute profile research using LangGraph deep research workflow.

        Args:
            query: User query about company profiles
            context: Context dict with services and metadata

        Returns:
            Result dict with report and metadata
        """
        # Validate and extract services
        services = self._validate_and_get_services(context)
        if not services:
            return {
                "response": "❌ Invalid context or missing LLM service",
                "metadata": {"error": "missing_context"},
            }

        llm_service, slack_service, channel = services
        logger.info(f"ProfileAgent executing deep research for: {query}")

        try:
            # Detect profile type and focus area
            profile_type, focus_area = await self._detect_profile_info(
                query, llm_service
            )

            # Setup progress tracking
            progress_msg_ts = await self._setup_progress_message(
                slack_service,
                channel,
                profile_type,
                context.get("thread_ts"),
                context.get("thinking_ts"),
            )

            # Initialize services
            internal_deep_research = await self._initialize_research_service()

            # Prepare graph configuration and input
            graph_config = self._prepare_graph_config(
                llm_service,
                internal_deep_research,
                context.get("thread_ts"),
                context.get("user_id", "unknown"),
            )
            input_state = self._create_input_state(query, profile_type, focus_area)

            # Execute graph with progress updates
            result = await self._execute_graph_with_progress(
                input_state, graph_config, slack_service, channel, progress_msg_ts
            )

            # Extract final state and report
            final_state = await self._extract_final_state(graph_config, result)
            final_report = final_state.get("final_report", "")
            executive_summary = final_state.get("executive_summary", "")
            notes_count = len(final_state.get("notes", []))

            if not final_report:
                return {
                    "response": "❌ Unable to generate profile report.",
                    "metadata": {
                        "error": "no_report",
                        "agent": "profile",
                        "query": query,
                        "profile_type": profile_type,
                    },
                }

            logger.info(
                f"Profile research complete: {len(final_report)} chars, {notes_count} notes"
            )

            # Cache report for follow-ups
            await self._cache_report(
                final_report,
                profile_type,
                query,
                context.get("thread_ts"),
                context.get("conversation_cache"),
            )

            # Generate PDF
            pdf_title = await self._generate_pdf_title(query)
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

            # Upload PDF to Slack
            pdf_uploaded = await self._upload_pdf_to_slack(
                slack_service,
                channel,
                pdf_bytes,
                pdf_title,
                profile_type,
                query,
                executive_summary,
                context.get("thread_ts"),
            )

            # Prepare response
            response_text = executive_summary if executive_summary else final_report
            response = "" if pdf_uploaded else response_text

            logger.info(
                f"PDF uploaded={pdf_uploaded}, returning {'empty' if pdf_uploaded else 'text'} response"
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
                    "clear_thread_tracking": True,
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
                    "profile_type": profile_type
                    if "profile_type" in locals()
                    else "unknown",
                },
            }


# Register agent with registry
agent_registry.register(
    name=ProfileAgent.name,
    agent_class=ProfileAgent,
    aliases=ProfileAgent.aliases,
)

logger.info(f"ProfileAgent registered: /{ProfileAgent.name}")

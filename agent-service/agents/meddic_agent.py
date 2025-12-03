"""MEDDIC Agent - Sales qualification and deal analysis.

Uses LangGraph to orchestrate MEDDPICC analysis workflow:
- Metrics: Quantifiable value
- Economic Buyer: Decision maker with budget
- Decision Criteria: Evaluation criteria
- Decision Process: How decisions are made
- Paper Process: Procurement and legal steps
- Identify Pain: Business problems
- Champion: Internal advocate
- Competition: Alternative vendors

REFACTORED VERSION: Giant run() method broken into focused helper methods.
"""

import logging
import time
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from agents.base_agent import BaseAgent
from agents.meddpicc_coach.configuration import MeddpiccConfiguration
from agents.meddpicc_coach.nodes.graph_builder import build_meddpicc_coach
from agents.meddpicc_coach.nodes.qa_collector import MEDDPICC_QUESTIONS
from agents.registry import agent_registry
from services.formatting import MessageFormatter
from services.meddpicc_context_manager import MeddpiccContextManager

logger = logging.getLogger(__name__)

# Singleton checkpoint saver - shared across all agent instances for state persistence
_checkpointer = None


class MeddicAgent(BaseAgent):
    """Agent for MEDDPICC sales qualification and coaching.

    Handles queries like:
    - "Analyze these sales call notes"
    - "MEDDPICC analysis for [notes]"
    - "Coach me on this deal: [notes]"

    Transforms unstructured sales notes into structured MEDDPICC framework
    with actionable coaching insights from the "MEDDPICC Maverick."
    """

    name = "meddic"
    aliases = ["medic", "meddpicc"]
    description = "MEDDPICC sales qualification and coaching - transforms sales notes into structured analysis with coaching insights"

    def __init__(self):
        """Initialize MeddicAgent with LangGraph workflow."""
        super().__init__()
        self.config = MeddpiccConfiguration.from_env()
        self.context_manager = MeddpiccContextManager()
        # Initialize singleton checkpointer and graph
        self._ensure_graph_initialized()
        logger.info("MeddicAgent initialized with singleton MemorySaver checkpointer")

    def _ensure_graph_initialized(self):
        """Ensure singleton checkpointer and graph are initialized."""
        global _checkpointer  # noqa: PLW0603
        if _checkpointer is None:
            # Create singleton MemorySaver - shared across all agent instances
            _checkpointer = MemorySaver()
            logger.info("✅ Initialized singleton MemorySaver checkpointer")

        if not hasattr(self, "graph") or self.graph is None:
            self.graph = build_meddpicc_coach(checkpointer=_checkpointer)
            logger.info("✅ Built MEDDPICC graph with singleton checkpointer")

    def _get_services_from_context(
        self, context: dict[str, Any]
    ) -> tuple[Any, str, str | None]:
        """Extract Slack service and channel from context.

        Args:
            context: Agent context dictionary

        Returns:
            Tuple of (slack_service, channel, thread_ts)
        """
        slack_service = context.get("slack_service")
        channel = context.get("channel")
        thread_ts = context.get("thread_ts")
        return slack_service, channel, thread_ts

    async def _setup_progress_message(
        self,
        slack_service: Any,
        channel: str,
        thread_ts: str | None,
        thinking_ts: str | None,
    ) -> str | None:
        """Setup initial progress message in Slack.

        Args:
            slack_service: Slack service
            channel: Slack channel
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
            text="🎯 *MEDDPICC Analysis Progress*\n\nAnalyzing your sales call notes...",
            thread_ts=thread_ts,
        )
        return progress_response.get("ts") if progress_response else None

    def _generate_thread_id(self, thread_ts: str | None, user_id: str) -> str:
        """Generate thread ID for LangGraph checkpointing.

        Args:
            thread_ts: Thread timestamp
            user_id: User ID

        Returns:
            Thread ID string
        """
        thread_id = thread_ts if thread_ts else f"meddic_{user_id}_{int(time.time())}"
        logger.info(f"🔗 Running MEDDPICC graph with thread_id: {thread_id}")
        return thread_id

    async def _load_previous_state(self, thread_id: str) -> dict[str, Any]:
        """Load previous state from checkpoint.

        Args:
            thread_id: Thread ID for checkpoint lookup

        Returns:
            Dictionary with previous state fields
        """
        checkpointer = self.graph.checkpointer
        try:
            checkpoint_tuple = await checkpointer.aget_tuple(
                {"configurable": {"thread_id": thread_id}}
            )

            # Initialize defaults
            state = {
                "conversation_history": None,
                "conversation_summary": None,
                "question_mode": False,
                "current_question_index": 0,
                "gathered_answers": {},
                "followup_mode": False,
                "original_analysis": "",
            }

            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                previous_state = checkpoint_tuple.checkpoint.get("channel_values", {})

                # Load conversation context
                state["conversation_history"] = previous_state.get(
                    "conversation_history", None
                )
                state["conversation_summary"] = previous_state.get(
                    "conversation_summary", None
                )

                # Load mode flags
                state["question_mode"] = previous_state.get("question_mode", False)
                state["current_question_index"] = previous_state.get(
                    "current_question_index", 0
                )
                state["gathered_answers"] = previous_state.get("gathered_answers", {})
                state["followup_mode"] = previous_state.get("followup_mode", False)
                state["original_analysis"] = previous_state.get("original_analysis", "")

            return state

        except Exception as e:
            logger.warning(f"Failed to load previous state: {e}")
            return {
                "conversation_history": None,
                "conversation_summary": None,
                "question_mode": False,
                "current_question_index": 0,
                "gathered_answers": {},
                "followup_mode": False,
                "original_analysis": "",
            }

    async def _build_input_state(
        self, query: str, previous_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Build input state based on conversation mode.

        Args:
            query: User query
            previous_state: Previous state from checkpoint

        Returns:
            Input state dictionary for graph execution
        """
        # Manage conversation context with compression
        context_result = await self.context_manager.manage_context(
            query,
            previous_state["conversation_history"],
            previous_state["conversation_summary"],
            role="user",
        )

        # Extract managed context
        conversation_history = context_result["conversation_history"]
        conversation_summary = context_result["conversation_summary"]
        enhanced_query = context_result["enhanced_query"]

        # Build input state based on mode
        if previous_state["followup_mode"]:
            # Follow-up questions mode - preserve state + context
            logger.info(
                f"💬 Continuing follow-up mode with {len(conversation_history)} messages in history"
            )
            return {
                "query": enhanced_query,
                "followup_mode": previous_state["followup_mode"],
                "original_analysis": previous_state["original_analysis"],
                "conversation_history": conversation_history,
                "conversation_summary": conversation_summary,
            }

        elif previous_state["question_mode"]:
            # Continuing Q&A - preserve Q&A state + context
            logger.info(
                f"📝 Continuing Q&A mode - question {previous_state['current_question_index']} of {len(MEDDPICC_QUESTIONS)}"
            )
            return {
                "query": query,  # Don't enhance Q&A answers
                "question_mode": previous_state["question_mode"],
                "current_question_index": previous_state["current_question_index"],
                "gathered_answers": previous_state["gathered_answers"],
                "conversation_history": conversation_history,
                "conversation_summary": conversation_summary,
            }

        else:
            # Regular analysis mode - use enhanced query with full context
            logger.info(
                f"🔍 Analysis mode with {len(conversation_history)} messages in history"
            )
            return {
                "query": enhanced_query,
                "conversation_history": conversation_history,
                "conversation_summary": conversation_summary,
                "followup_mode": previous_state["followup_mode"],
                "original_analysis": previous_state["original_analysis"],
            }

    def _get_node_messages(self) -> dict[str, dict[str, str]]:
        """Get node progress messages configuration.

        Returns:
            Dictionary mapping node names to start/complete messages
        """
        return {
            "parse_notes": {
                "start": "📝 Parsing notes and extracting URLs...",
                "complete": "✅ Notes parsed",
            },
            "meddpicc_analysis": {
                "start": "🔍 Structuring MEDDPICC breakdown...",
                "complete": "✅ MEDDPICC analysis complete",
            },
            "coaching_insights": {
                "start": "🎓 Generating coaching insights...",
                "complete": "✅ Coaching complete",
            },
            "followup_handler": {
                "start": "💬 Processing your follow-up question...",
                "complete": "✅ Response ready",
            },
        }

    def _get_node_order(self) -> list[str]:
        """Get ordered list of graph nodes.

        Returns:
            List of node names in execution order
        """
        return ["parse_notes", "meddpicc_analysis", "coaching_insights"]

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
        node_messages = self._get_node_messages()
        node_order = self._get_node_order()

        # Initialize tracking structures
        completed_steps = []
        node_start_times = {}
        node_durations = {}
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
                    text=f"🎯 *MEDDPICC Analysis Progress*\n\n{node_messages[node_order[0]]['start']}",
                )

            # Process node completion events
            if isinstance(event, dict):
                for node_name, _node_data in event.items():
                    if node_name in node_messages:
                        # Calculate duration
                        end_time = time.time()
                        start_time = node_start_times.get(node_name)
                        duration = end_time - start_time if start_time else 0
                        node_durations[node_name] = duration

                        duration_text = f" ({duration:.1f}s)" if duration > 0 else ""
                        completed_steps.append(
                            f"{node_messages[node_name]['complete']}{duration_text}"
                        )
                        logger.info(
                            f"✅ Completed node: {node_name} in {duration:.1f}s"
                        )

                        # Show next in-progress step
                        if slack_service and channel and progress_msg_ts:
                            all_steps = list(completed_steps)

                            # Determine next node
                            try:
                                current_index = node_order.index(node_name)
                                if current_index + 1 < len(node_order):
                                    next_node = node_order[current_index + 1]
                                    node_start_times[next_node] = time.time()
                                    all_steps.append(node_messages[next_node]["start"])
                            except (ValueError, IndexError):
                                pass

                            steps_text = "\n".join(all_steps)
                            await slack_service.update_message(
                                channel=channel,
                                ts=progress_msg_ts,
                                text=f"🎯 *MEDDPICC Analysis Progress*\n\n{steps_text}",
                            )

            result = event

        return result

    def _extract_final_result(self, result: Any) -> dict[str, Any]:
        """Extract final result from graph execution.

        Args:
            result: Final event from graph execution

        Returns:
            Final result dictionary
        """
        if result and isinstance(result, dict):
            values = list(result.values())
            result = values[0] if values else {}

        if not isinstance(result, dict):
            logger.error(f"Invalid result type: {type(result)}")
            result = {}

        return result

    def _handle_question_mode(self, result: dict[str, Any]) -> dict[str, Any] | None:
        """Handle Q&A mode response.

        Args:
            result: Final result dictionary

        Returns:
            Response dictionary if in Q&A mode, None otherwise
        """
        question_mode = result.get("question_mode", False)
        if not question_mode:
            return None

        logger.info("Graph is in Q&A mode - returning question to user")
        final_response = result.get("final_response", "")

        return {
            "response": final_response,
            "metadata": {
                "agent": "meddic",
                "question_mode": True,
                "agent_type": "meddpicc_coach",
                "agent_version": "langgraph",
            },
        }

    def _handle_clarification_needed(
        self, result: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Handle clarification request.

        Args:
            result: Final result dictionary

        Returns:
            Response dictionary if clarification needed, None otherwise
        """
        clarification_message = result.get("clarification_message")
        if not clarification_message:
            return None

        logger.info("Input requires clarification - returning clarification message")

        # Ensure header is present
        if not clarification_message.startswith(":dart:"):
            clarification_message = f":dart: **MEDDPICC**\n\n{clarification_message}"

        return {
            "response": clarification_message,
            "metadata": {
                "needs_clarification": True,
                "agent": "meddic",
                "agent_type": "meddpicc_coach",
                "agent_version": "langgraph",
            },
        }

    def _format_final_response(
        self,
        result: dict[str, Any],
        query: str,
        thread_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Format and return final response.

        Args:
            result: Final result dictionary
            query: Original query
            thread_id: Thread ID
            context: Original context

        Returns:
            Final response dictionary
        """
        final_response = result.get("final_response", "")
        sources = result.get("sources", [])

        if not final_response:
            return {
                "response": "❌ Unable to generate MEDDPICC analysis. Please try again with your sales call notes.",
                "metadata": {
                    "error": "no_response",
                    "agent": "meddic",
                },
            }

        logger.info(f"MEDDPICC analysis complete: {len(final_response)} chars")

        # Convert markdown to Slack-compatible format
        slack_formatted_response = MessageFormatter.format_markdown_for_slack(
            final_response
        )

        # Check if we should clear thread tracking
        followup_mode_state = result.get("followup_mode")
        should_clear_tracking = followup_mode_state is False

        # Add session completion footer
        if should_clear_tracking:
            session_footer = "\n\n---\n\n_✅ Feel free to ask me anything!_"
        else:
            session_footer = (
                "\n\n---\n\n_💬 Ask me follow-up questions or type 'done' to exit._"
            )

        response = slack_formatted_response + session_footer

        logger.info(
            f"✅ Returning formatted markdown response (clear_tracking={should_clear_tracking})"
        )

        metadata = {
            "agent": "meddic",
            "agent_type": "meddpicc_coach",
            "agent_version": "langgraph",
            "query_length": len(query),
            "response_length": len(final_response),
            "sources_count": len(sources),
            "user_id": context.get("user_id"),
            "thread_id": thread_id,
        }

        # Only clear thread tracking if user explicitly exited follow-up mode
        if should_clear_tracking:
            metadata["clear_thread_tracking"] = True
            logger.info("User exited follow-up mode - clearing thread tracking")

        return {
            "response": response,
            "metadata": metadata,
        }

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute MEDDPICC analysis using LangGraph.

        Args:
            query: Sales call notes to analyze
            context: Context dict with services and metadata

        Returns:
            Result dict with structured MEDDPICC analysis
        """
        if not self.validate_context(context):
            return {
                "response": "❌ Invalid context for MEDDIC agent",
                "metadata": {"error": "missing_context"},
            }

        logger.info(f"MeddicAgent executing with query length: {len(query)} chars")

        # Ensure graph is initialized
        self._ensure_graph_initialized()

        # Get services from context
        slack_service, channel, thread_ts = self._get_services_from_context(context)

        # Setup progress message
        progress_msg_ts = await self._setup_progress_message(
            slack_service, channel, thread_ts, context.get("thinking_ts")
        )

        try:
            # Generate thread ID
            thread_id = self._generate_thread_id(
                thread_ts, context.get("user_id", "unknown")
            )

            # Load previous state and build input state
            previous_state = await self._load_previous_state(thread_id)
            input_state = await self._build_input_state(query, previous_state)

            logger.info(
                f"📊 Input state: query={len(input_state.get('query', ''))} chars, "
                f"question_mode={input_state.get('question_mode', False)}, "
                f"followup_mode={input_state.get('followup_mode', False)}"
            )

            # Prepare graph configuration
            graph_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "document_content": context.get("document_content", ""),
                }
            }

            # Execute graph with progress updates
            result = await self._execute_graph_with_progress(
                input_state, graph_config, slack_service, channel, progress_msg_ts
            )

            # Extract final result
            final_result = self._extract_final_result(result)

            # Handle Q&A mode
            qa_response = self._handle_question_mode(final_result)
            if qa_response:
                return qa_response

            # Handle clarification needed
            clarification_response = self._handle_clarification_needed(final_result)
            if clarification_response:
                return clarification_response

            # Format and return final response
            return self._format_final_response(final_result, query, thread_id, context)

        except Exception as e:
            logger.error(f"MeddicAgent error: {e}", exc_info=True)
            return {
                "response": (
                    f"❌ Error during MEDDPICC analysis: {str(e)}\n\n"
                    f"Please try again with your sales call notes."
                ),
                "metadata": {
                    "error": str(e),
                    "agent": "meddic",
                },
            }


# Register agent with registry
agent_registry.register(
    name=MeddicAgent.name,
    agent_class=MeddicAgent,
    aliases=MeddicAgent.aliases,
)

logger.info(f"MeddicAgent registered: /{MeddicAgent.name}")

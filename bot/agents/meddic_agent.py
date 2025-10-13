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
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent
from agents.meddpicc_coach.configuration import MeddpiccConfiguration
from agents.meddpicc_coach.meddpicc_coach import meddpicc_coach
from agents.registry import agent_registry

logger = logging.getLogger(__name__)


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
        self.graph = meddpicc_coach
        logger.info("MeddicAgent initialized with MEDDPICC coach workflow")

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute MEDDPICC analysis using LangGraph.

        Args:
            query: Sales call notes to analyze
            context: Context dict with user_id, channel, slack_service, etc.

        Returns:
            Result dict with structured MEDDPICC analysis and coaching
        """
        if not self.validate_context(context):
            return {
                "response": "❌ Invalid context for MEDDIC agent",
                "metadata": {"error": "missing_context"},
            }

        logger.info(f"MeddicAgent executing with query length: {len(query)} chars")
        logger.info(f"MeddicAgent query content: '{query}'")

        # Get services from context
        slack_service = context.get("slack_service")
        channel = context.get("channel")
        thread_ts = context.get("thread_ts")

        # Delete thinking indicator and send initial progress message
        progress_msg_ts = None
        if slack_service and channel:
            # Remove thinking indicator first
            thinking_ts = context.get("thinking_ts")
            if thinking_ts:
                await slack_service.delete_thinking_indicator(channel, thinking_ts)

            # Send initial progress message
            progress_response = await slack_service.send_message(
                channel=channel,
                text="🎯 *MEDDPICC Analysis Progress*\n\nAnalyzing your sales call notes...",
                thread_ts=thread_ts,
            )
            progress_msg_ts = progress_response.get("ts") if progress_response else None

        try:
            # Prepare LangGraph configuration
            # Pass document content from context (extracted by main handler from file attachments)
            # Use thread_ts as the LangGraph thread_id for state persistence
            import time

            thread_id = (
                thread_ts
                if thread_ts
                else f"meddic_{context.get('user_id')}_{int(time.time())}"
            )
            logger.info(f"🔗 Running MEDDPICC graph with thread_id: {thread_id}")

            # Check for previous checkpoint to restore Q&A state and accumulate context
            from agents.meddpicc_coach.nodes.qa_collector import MEDDPICC_QUESTIONS

            accumulated_query = query
            input_state = {"query": query}

            # Use the checkpointer from the graph
            checkpointer = self.graph.checkpointer

            try:
                # Attempt to load previous state from checkpoint
                checkpoint_tuple = await checkpointer.aget_tuple(
                    {"configurable": {"thread_id": thread_id}}
                )

                if checkpoint_tuple and checkpoint_tuple.checkpoint:
                    previous_state = checkpoint_tuple.checkpoint.get(
                        "channel_values", {}
                    )

                    # Check if we're continuing a Q&A session
                    question_mode = previous_state.get("question_mode", False)
                    current_question_index = previous_state.get(
                        "current_question_index", 0
                    )
                    gathered_answers = previous_state.get("gathered_answers", {})

                    # Check if we're in follow-up questions mode (after analysis complete)
                    followup_mode = previous_state.get("followup_mode", False)
                    original_analysis = previous_state.get("original_analysis", "")

                    if followup_mode:
                        # Follow-up questions mode - preserve follow-up state
                        logger.info(
                            f"💬 Continuing follow-up questions mode - user asked: {query[:50]}..."
                        )
                        input_state = {
                            "query": query,  # User's follow-up question
                            "followup_mode": followup_mode,
                            "original_analysis": original_analysis,
                        }
                    elif question_mode:
                        # Continuing Q&A - preserve Q&A state fields
                        logger.info(
                            f"📝 Continuing Q&A mode - question {current_question_index} of {len(MEDDPICC_QUESTIONS)}"
                        )
                        input_state = {
                            "query": query,  # User's answer to the current question
                            "question_mode": question_mode,
                            "current_question_index": current_question_index,
                            "gathered_answers": gathered_answers,
                        }
                    else:
                        # Regular analysis mode - accumulate context
                        previous_query = previous_state.get("query", "")
                        if previous_query and previous_query != query:
                            accumulated_query = f"{previous_query}\n\n---\n\n**Additional information:**\n{query}"
                            logger.info(
                                f"📚 Accumulated context from previous turn ({len(previous_query)} + {len(query)} chars)"
                            )
                            input_state = {"query": accumulated_query}
                        else:
                            logger.info(
                                "🆕 First message in thread (no previous context)"
                            )
                else:
                    logger.info("🆕 No previous checkpoint found (new conversation)")
            except Exception as e:
                logger.warning(
                    f"Failed to load checkpoint for context accumulation: {e}"
                )
                # Continue with just the new query

            # Log the input state
            logger.info(
                f"📊 Input state: query={len(input_state.get('query', ''))} chars, question_mode={input_state.get('question_mode', False)}, followup_mode={input_state.get('followup_mode', False)}"
            )

            graph_config = {
                "configurable": {
                    "thread_id": thread_id,  # Enable checkpointing
                    "document_content": context.get("document_content", ""),
                }
            }

            # Map node names to user-friendly progress messages
            node_messages = {
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

            # Track completed steps
            completed_steps = []
            node_order = ["parse_notes", "meddpicc_analysis", "coaching_insights"]

            # Track timing
            import time

            node_start_times = {}
            node_durations = {}

            # Show first node as starting
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
                        text=f"🎯 *MEDDPICC Analysis Progress*\n\n{node_messages[node_order[0]]['start']}",
                    )

                # Extract node name from event
                if isinstance(event, dict):
                    for node_name, _node_data in event.items():
                        if node_name in node_messages:
                            # Calculate duration
                            end_time = time.time()
                            start_time = node_start_times.get(node_name)
                            duration = end_time - start_time if start_time else 0
                            node_durations[node_name] = duration

                            # Format duration
                            duration_text = (
                                f" ({duration:.1f}s)" if duration > 0 else ""
                            )

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
                                        all_steps.append(
                                            node_messages[next_node]["start"]
                                        )
                                except (ValueError, IndexError):
                                    pass

                                steps_text = "\n".join(all_steps)
                                await slack_service.update_message(
                                    channel=channel,
                                    ts=progress_msg_ts,
                                    text=f"🎯 *MEDDPICC Analysis Progress*\n\n{steps_text}",
                                )

                # Store last event
                result = event

            # Extract final state
            if result and isinstance(result, dict):
                values = list(result.values())
                result = values[0] if values else {}

            if not isinstance(result, dict):
                logger.error(f"Invalid result type: {type(result)}")
                result = {}

            # Check if we're in Q&A mode (graph is asking questions)
            question_mode = result.get("question_mode", False)
            if question_mode:
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

            # Check if clarification is needed (early-stage minimal input)
            clarification_message = result.get("clarification_message")
            if clarification_message:
                logger.info(
                    "Input requires clarification - returning clarification message"
                )

                # Ensure header is present
                if not clarification_message.startswith(":dart:"):
                    clarification_message = (
                        f":dart: **MEDDPICC**\n\n{clarification_message}"
                    )

                return {
                    "response": clarification_message,
                    "metadata": {
                        "needs_clarification": True,
                        "agent": "meddic",
                        "agent_type": "meddpicc_coach",
                        "agent_version": "langgraph",
                    },
                }

            # Extract final response
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

            # Convert markdown to Slack-compatible format and return directly
            from services.formatting import MessageFormatter

            slack_formatted_response = MessageFormatter.format_markdown_for_slack(
                final_response
            )

            # Check if we should clear thread tracking
            # If followup_mode is False, user exited follow-up mode (asked unrelated question)
            # If followup_mode is True or None, keep tracking for continued conversation
            followup_mode_state = result.get("followup_mode")
            should_clear_tracking = followup_mode_state is False

            # Add session completion footer only if exiting
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

logger.info(
    f"MeddicAgent registered: /{MeddicAgent.name} (aliases: {MeddicAgent.aliases})"
)

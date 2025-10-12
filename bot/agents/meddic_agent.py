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

        logger.info(f"MeddicAgent executing MEDDPICC analysis ({len(query)} chars)")

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

            # Check for previous checkpoint to accumulate context across turns
            from agents.meddpicc_coach.nodes.graph_builder import get_checkpointer

            accumulated_query = query
            checkpointer = get_checkpointer()

            try:
                # Attempt to load previous state from checkpoint
                checkpoint_tuple = await checkpointer.aget_tuple(
                    {"configurable": {"thread_id": thread_id}}
                )
                if checkpoint_tuple and checkpoint_tuple.checkpoint:
                    previous_state = checkpoint_tuple.checkpoint.get(
                        "channel_values", {}
                    )
                    previous_query = previous_state.get("query", "")

                    if previous_query and previous_query != query:
                        # Accumulate: previous context + new information
                        accumulated_query = f"{previous_query}\n\n---\n\n**Additional information:**\n{query}"
                        logger.info(
                            f"📚 Accumulated context from previous turn ({len(previous_query)} + {len(query)} chars)"
                        )
                    else:
                        logger.info("🆕 First message in thread (no previous context)")
                else:
                    logger.info("🆕 No previous checkpoint found (new conversation)")
            except Exception as e:
                logger.warning(
                    f"Failed to load checkpoint for context accumulation: {e}"
                )
                # Continue with just the new query

            # Prepare input state with accumulated context
            input_state = {"query": accumulated_query}

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

            # Check if clarification is needed (early-stage minimal input)
            clarification_message = result.get("clarification_message")
            if clarification_message:
                logger.info(
                    "Input requires clarification - returning clarification message"
                )
                # Delete progress indicator
                if slack_service and channel and progress_msg_ts:
                    try:
                        await slack_service.delete_message(
                            channel=channel, ts=progress_msg_ts
                        )
                    except Exception as e:
                        logger.warning(f"Failed to delete progress message: {e}")

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

            # Delete progress indicator
            if slack_service and channel and progress_msg_ts:
                await slack_service.delete_message(channel, progress_msg_ts)

            # Generate PDF with entity extraction for title
            from datetime import datetime

            from utils.pdf_generator import get_pdf_filename, markdown_to_pdf

            # Extract company/person name from notes for better title
            pdf_title = "MEDDPICC Sales Analysis"
            try:
                import json

                from langchain_openai import ChatOpenAI

                from config.settings import LLMSettings

                llm_settings = LLMSettings()

                extraction_prompt = f"""Extract the company or person name from these sales notes and return as JSON.

Notes: "{query[:500]}"

Examples:
- "Call with Sarah from Acme Corp..." → {{"entity": "Acme Corp"}}
- "Meeting with John at TechStartup..." → {{"entity": "TechStartup"}}
- "DataCorp wants to improve..." → {{"entity": "DataCorp"}}
- "Discussed with Jennifer Martinez at GlobalTech..." → {{"entity": "GlobalTech"}}

Return ONLY JSON: {{"entity": "name here"}}"""

                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=llm_settings.api_key.get_secret_value(),
                    temperature=0.0,
                    max_completion_tokens=30,
                )

                entity_response = await llm.ainvoke(extraction_prompt)
                entity_text = entity_response.content.strip()
                entity_data = json.loads(entity_text)
                entity_name = entity_data.get("entity", "").strip()

                if entity_name and len(entity_name) > 0 and len(entity_name) < 100:
                    pdf_title = f"{entity_name} - MEDDPICC Analysis"
                    logger.info(f"✅ Using extracted entity: '{pdf_title}'")
                else:
                    logger.warning("⚠️ Entity name invalid, using generic title")

            except Exception as e:
                logger.warning(f"Entity extraction failed: {e}, using generic title")

            pdf_metadata = {
                "Query Length": f"{len(query)} characters",
                "Sources": f"{len(sources)} URL(s)" if sources else "Text notes only",
                "Generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            pdf_bytes = markdown_to_pdf(
                markdown_content=final_response,
                title=pdf_title,
                metadata=pdf_metadata,
                style="professional",
            )

            # Extract executive summary (first part before "---")
            executive_summary = ""
            if "---" in final_response:
                parts = final_response.split("---", 1)
                # Take MEDDPICC breakdown (everything before coaching)
                executive_summary = parts[0].strip()

            # Upload PDF to Slack with summary
            pdf_uploaded = False
            if slack_service and channel:
                try:
                    pdf_filename = get_pdf_filename(
                        title=f"MEDDPICC_Analysis_{datetime.now().strftime('%Y%m%d')}",
                        profile_type="meddpicc",
                    )

                    # Use executive summary as initial comment with session completion footer
                    if executive_summary:
                        session_footer = "\n\n---\n\n_✅ MEDDPICC analysis complete! Type `-meddic` to start a new analysis._"
                        initial_comment = executive_summary[:1000] + session_footer
                    else:
                        initial_comment = None

                    upload_response = await slack_service.upload_file(
                        channel=channel,
                        file_content=pdf_bytes,
                        filename=pdf_filename,
                        title=pdf_title,
                        initial_comment=initial_comment,
                        thread_ts=thread_ts,
                    )

                    if upload_response:
                        pdf_uploaded = True
                        logger.info(f"PDF report uploaded: {pdf_filename}")
                    else:
                        logger.warning("Failed to upload PDF to Slack")

                except Exception as pdf_error:
                    logger.error(f"Error uploading PDF: {pdf_error}")

            # If PDF uploaded, return empty (summary already posted)
            # Otherwise return full text
            # Add session completion footer (analysis complete, auto-exit)
            session_footer = "\n\n---\n\n_✅ MEDDPICC analysis complete! Type `-meddic` to start a new analysis._"

            if pdf_uploaded:
                response = ""
                logger.info("✅ PDF uploaded with summary, returning empty response")
            else:
                response = final_response + session_footer
                logger.info("⚠️ PDF upload failed, returning text fallback")

            return {
                "response": response,
                "metadata": {
                    "agent": "meddic",
                    "agent_type": "meddpicc_coach",
                    "agent_version": "langgraph",
                    "query_length": len(query),
                    "response_length": len(final_response),
                    "sources_count": len(sources),
                    "pdf_generated": pdf_bytes is not None,
                    "pdf_uploaded": pdf_uploaded,
                    "user_id": context.get("user_id"),
                    "thread_id": thread_id,
                    # Auto-clear thread tracking after full analysis
                    # User needs to type -meddic to start a new session
                    "clear_thread_tracking": True,
                },
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

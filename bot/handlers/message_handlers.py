import contextlib
import logging
import os

# Import document processor from ingest module
import sys
import time

from handlers.agent_processes import get_agent_blocks, run_agent_process
from services.formatting import MessageFormatter
from services.llm_service import LLMService
from services.metrics_service import get_metrics_service
from services.slack_file_service import SlackFileService
from services.slack_service import SlackService
from utils.errors import handle_error

sys.path.append(os.path.join(os.path.dirname(__file__), "../../ingest"))
from services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_MESSAGE = """You are Insight Mesh, an intelligent AI assistant powered by advanced RAG (Retrieval-Augmented Generation) technology. Your primary purpose is to help users explore, understand, and work with their organization's knowledge base and data.

## Core Capabilities:
- **Knowledge Retrieval**: You search through ingested documents using hybrid retrieval (combining semantic similarity and keyword matching) to provide accurate, context-aware responses
- **Source Attribution**: You always cite the specific documents that inform your responses, showing users exactly where information comes from
- **Thread Awareness**: You maintain conversation context across Slack threads and can reference previous messages in ongoing discussions
- **Agent Processes**: You can trigger background data processing jobs when users need to index documents, import data, or run other automated tasks

## Communication Style:
- Be conversational, helpful, and concise
- Use clear, professional language appropriate for workplace collaboration
- When using retrieved context, integrate it naturally into your responses without awkward transitions
- If you're unsure about something, say so honestly rather than guessing

## How You Handle Information:
- When relevant documents are found, use that information as your primary source and cite it properly
- If no relevant context is retrieved, clearly indicate you're responding based on general knowledge
- Always prioritize accuracy over completeness - it's better to say "I don't have information about that in the knowledge base" than to speculate
- Maintain conversation flow while being transparent about your sources

## Slack Behavior:
- You automatically participate in threads once mentioned, no need for users to @mention you again in the same thread
- You show typing indicators while processing requests
- You work in all Slack contexts: DMs, channels, and group conversations

Remember: Your strength lies in connecting users with their organization's documented knowledge while providing intelligent, contextual assistance."""

# Constants
HTTP_OK = 200


def get_user_system_prompt() -> str:
    """Get the default system prompt"""
    return DEFAULT_SYSTEM_MESSAGE


async def handle_message(
    text: str,
    user_id: str,
    slack_service: SlackService,
    llm_service: LLMService,
    channel: str,
    thread_ts: str | None = None,
    files: list[dict] | None = None,
    conversation_cache=None,
):
    """Handle an incoming message from Slack"""
    start_time = time.time()

    logger.info(
        "Processing user message",
        extra={
            "user_message": text,
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": thread_ts,
            "event_type": "user_message",
        },
    )

    # Record message processing metric
    metrics_service = get_metrics_service()
    if metrics_service:
        metrics_service.record_message_processed(
            user_id=user_id, channel_type="dm" if channel.startswith("D") else "channel"
        )

        # Track active conversations with proper conversation ID
        # Use thread_ts for threaded conversations, otherwise use channel
        # This matches the conversation_id used by LLM service for Langfuse tracing
        conversation_id = thread_ts or channel
        metrics_service.record_conversation_activity(conversation_id)

        # Categorize query type for metrics
        query_category = "question"  # Default
        if text.lower().startswith(("run ", "execute ", "start ")):
            query_category = "command"
        elif thread_ts:  # In a thread, likely continuing conversation
            query_category = "conversation"

        has_context = bool(thread_ts)  # Has conversation context
        metrics_service.record_query_type(query_category, has_context)

    # For tracking the thinking indicator message
    thinking_message_ts = None

    try:
        # Show typing indicator (skip if method doesn't exist)
        # Note: Typing indicators are handled by Slack automatically in most cases

        # Handle agent process commands
        if text.strip().lower().startswith("start "):
            agent_process_name = text.strip().lower()[6:]
            if agent_process_name:
                logger.info(f"Starting agent process: {agent_process_name}")

                try:
                    # First send thinking message
                    thinking_message_ts = await slack_service.send_thinking_indicator(
                        channel, thread_ts
                    )

                    # Run the agent process
                    response = await run_agent_process(
                        process_name=agent_process_name,
                        slack_service=slack_service,
                        channel_id=channel,
                        thread_ts=thread_ts,
                    )

                    # Clean up thinking message before sending response
                    if thinking_message_ts:
                        try:
                            await slack_service.delete_thinking_indicator(
                                channel, thinking_message_ts
                            )
                            thinking_message_ts = None
                        except Exception as e:
                            logger.warning(f"Error deleting thinking message: {e}")

                    # Send response with agent blocks
                    formatted_response = await MessageFormatter.format_message(response)
                    agent_blocks = get_agent_blocks()

                    await slack_service.send_message(
                        channel=channel,
                        text=formatted_response,
                        blocks=agent_blocks,
                        thread_ts=thread_ts,
                    )

                except Exception as e:
                    # Clean up thinking message on error
                    if thinking_message_ts:
                        with contextlib.suppress(Exception):
                            await slack_service.delete_thinking_indicator(
                                channel, thinking_message_ts
                            )

                    logger.error(f"Agent process failed: {e}")
                    error_response = (
                        f"❌ Agent process '{agent_process_name}' failed: {str(e)}"
                    )
                    await slack_service.send_message(
                        channel=channel, text=error_response, thread_ts=thread_ts
                    )
                return

        # Regular LLM response handling
        try:
            # First send thinking message
            thinking_message_ts = await slack_service.send_thinking_indicator(
                channel, thread_ts
            )
        except Exception as e:
            logger.error(f"Error posting thinking message: {e}")

        # Process attached files if present
        document_content = ""
        if files:
            file_service = SlackFileService(slack_service.client)
            doc_processor = DocumentProcessor()

            for file_info in files:
                if file_service.is_processable_file(file_info):
                    logger.info(f"Processing file: {file_info.get('name', 'unknown')}")

                    # Download file content
                    file_content = await file_service.download_file_content(file_info)
                    if file_content:
                        # Extract text from document
                        extracted_text = doc_processor.extract_text(
                            file_content, file_info.get("mimetype", "")
                        )
                        if extracted_text:
                            file_name = file_info.get("name", "unknown file")
                            document_content += f"\n\n--- Content from {file_name} ---\n{extracted_text}"
                            logger.info(
                                f"Extracted {len(extracted_text)} characters from {file_name}"
                            )
                        else:
                            logger.warning(
                                f"Could not extract text from {file_info.get('name')}"
                            )
                    else:
                        logger.warning(
                            f"Could not download file {file_info.get('name')}"
                        )
                else:
                    logger.info(
                        f"Skipping unsupported file type: {file_info.get('mimetype')}"
                    )

        # Get the thread history for context
        history, should_use_thread_context = await slack_service.get_thread_history(
            channel, thread_ts
        )

        if should_use_thread_context:
            logger.info(
                f"Using thread context with {len(history)} messages for response generation"
            )

        # Add document content to cache if present and cache is available
        if document_content and conversation_cache and thread_ts:
            document_message = {
                "role": "user",
                "content": f"[Document content shared by user]{document_content}",
            }
            await conversation_cache.update_conversation(
                thread_ts, document_message, is_bot_message=False
            )
            logger.info(
                f"Added document content to conversation cache for thread {thread_ts}"
            )

        # Prepare current query with document content if present
        current_query = text
        if document_content:
            current_query = f"{text}{document_content}"
            logger.info(
                f"Enhanced query with {len(document_content)} characters of document content"
            )

        # Generate response using LLM service
        response = await llm_service.get_response(
            messages=history,
            user_id=user_id,
            current_query=current_query,
        )

        # Clean up thinking message
        if thinking_message_ts:
            try:
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )
            except Exception as e:
                logger.warning(f"Error deleting thinking message: {e}")

        # Format and send the response
        if response:
            formatted_response = await MessageFormatter.format_message(response)
            await slack_service.send_message(
                channel=channel, text=formatted_response, thread_ts=thread_ts
            )
        else:
            await slack_service.send_message(
                channel=channel,
                text="I apologize, but I couldn't generate a response. Please try again.",
                thread_ts=thread_ts,
            )

        # Record successful request timing
        if metrics_service:
            duration = time.time() - start_time
            metrics_service.request_duration.labels(
                endpoint="message_handler", method="POST"
            ).observe(duration)

    except Exception as e:
        # Clean up thinking message on error
        if thinking_message_ts:
            with contextlib.suppress(Exception):
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )

        await handle_error(
            slack_service.client,
            channel,
            thread_ts,
            e,
            "I'm sorry, I encountered an error while processing your message.",
        )

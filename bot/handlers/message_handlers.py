"""Simplified message handlers - thin Slack adapter to rag-service.

All business logic (routing, RAG, LLM) is now in rag-service.
This module only handles Slack-specific operations:
- File processing
- Message formatting
- Thinking indicators
- Thread management
"""

import contextlib
import logging
import time
from typing import Any

from handlers.file_processors import process_file_attachments
from handlers.prompt_manager import get_user_system_prompt
from services.formatting import MessageFormatter
from services.langfuse_service import get_langfuse_service
from services.metrics_service import get_metrics_service
from services.rag_client import get_rag_client
from services.slack_service import SlackService
from utils.errors import handle_error

logger = logging.getLogger(__name__)


# Helper functions


def _determine_conversation_id(
    channel: str, thread_ts: str | None, message_ts: str | None
) -> str:
    """Determine unique conversation ID based on context.

    Args:
        channel: Slack channel ID
        thread_ts: Thread timestamp (if in thread)
        message_ts: Message timestamp (for non-threaded mentions)

    Returns:
        Unique conversation ID

    Raises:
        ValueError: If non-DM message lacks both thread_ts and message_ts
    """
    is_dm = channel.startswith("D")

    if thread_ts:
        return thread_ts  # Threaded conversation
    elif is_dm:
        return channel  # DM conversation (channel is unique per user)
    elif message_ts:
        return message_ts  # Non-threaded mention (each is separate)
    else:
        raise ValueError("Must provide thread_ts or message_ts for non-DM messages")


def _record_message_metrics(
    user_id: str,
    channel: str,
    text: str,
    conversation_id: str,
    thread_ts: str | None,
) -> None:
    """Record message processing metrics.

    Args:
        user_id: Slack user ID
        channel: Slack channel ID
        text: Message text
        conversation_id: Unique conversation identifier
        thread_ts: Thread timestamp (optional)
    """
    metrics_service = get_metrics_service()
    if not metrics_service:
        return

    # Record message processed
    metrics_service.record_message_processed(
        user_id=user_id, channel_type="dm" if channel.startswith("D") else "channel"
    )

    # Track conversation activity
    metrics_service.record_conversation_activity(conversation_id)

    # Categorize query type
    query_category = "question"  # Default
    if text.lower().startswith(("run ", "execute ", "start ")):
        query_category = "command"
    elif thread_ts:  # In a thread, likely continuing conversation
        query_category = "conversation"

    has_context = bool(thread_ts)
    metrics_service.record_query_type(query_category, has_context)


async def _process_and_cache_files(
    files: list[dict[str, Any]] | None,
    slack_service: SlackService,
    conversation_cache: Any | None,
    thread_ts: str | None,
) -> tuple[str, str | None]:
    """Process file attachments and cache document content.

    Args:
        files: List of file attachments
        slack_service: Slack service instance
        conversation_cache: Conversation cache instance
        thread_ts: Thread timestamp

    Returns:
        Tuple of (document_content, document_filename)
    """
    document_content = ""
    document_filename = None

    if files:
        logger.info(f"Files attached: {[f.get('name', 'unknown') for f in files]}")
        document_content = await process_file_attachments(files, slack_service)
        document_filename = files[0].get("name") if files else None

        if document_content:
            logger.info(
                f"Extracted {len(document_content)} characters from {len(files)} file(s)"
            )

            # Store in cache
            if conversation_cache and thread_ts:
                await conversation_cache.store_document_content(
                    thread_ts, document_content, document_filename or "unknown"
                )

    # Check for previously stored documents in thread
    elif thread_ts and conversation_cache:
        stored_content, stored_filename = await conversation_cache.get_document_content(
            thread_ts
        )
        if stored_content:
            document_content = stored_content
            document_filename = stored_filename
            logger.info(
                f"Retrieved previously stored document for thread {thread_ts}: {stored_filename}"
            )

    return document_content, document_filename


async def _determine_rag_setting(
    thread_ts: str | None,
    conversation_cache: Any | None,
    document_filename: str | None,
) -> bool:
    """Determine whether to use RAG for this conversation.

    Args:
        thread_ts: Thread timestamp
        conversation_cache: Conversation cache instance
        document_filename: Document filename (optional)

    Returns:
        True if RAG should be enabled, False otherwise
    """
    if not (thread_ts and conversation_cache):
        return True  # Default to RAG enabled

    thread_type = await conversation_cache.get_thread_type(thread_ts)
    logger.info(
        f"Thread {thread_ts}: type={thread_type}, has_cache={conversation_cache is not None}"
    )

    is_profile_thread = thread_type == "profile"
    use_rag = not is_profile_thread

    logger.info(
        f"Thread {thread_ts}: is_profile_thread={is_profile_thread}, use_rag={use_rag}, "
        f"has_document={document_filename is not None}"
    )

    if is_profile_thread:
        logger.info(
            f"✅ Disabling RAG for profile thread {thread_ts} (document: {document_filename})"
        )
    else:
        logger.info(
            f"📚 RAG enabled for thread {thread_ts} (thread_type={thread_type})"
        )

    return use_rag


# Main message handler


async def handle_message(
    text: str,
    user_id: str,
    slack_service: SlackService,
    channel: str,
    thread_ts: str | None = None,
    files: list[dict[str, Any]] | None = None,
    conversation_cache: Any | None = None,
    message_ts: str | None = None,
) -> None:
    """
    Handle an incoming message from Slack.

    This is now a THIN ADAPTER - all business logic is in rag-service.
    This function only handles Slack-specific operations:
    - File processing (Slack API)
    - User prompt management (Slack user settings)
    - Thread history (Slack API)
    - Formatting (Slack markdown)
    - Sending (Slack API)

    Args:
        text: Message text
        user_id: Slack user ID
        slack_service: Slack service instance
        channel: Slack channel ID
        thread_ts: Thread timestamp (optional)
        files: List of file attachments (optional)
        conversation_cache: Conversation cache instance (optional)
        message_ts: Message timestamp - used as unique conversation ID when not in thread
    """
    start_time = time.time()

    # Determine unique conversation ID
    conversation_id = _determine_conversation_id(channel, thread_ts, message_ts)

    logger.info(
        "Processing user message",
        extra={
            "user_message": text,
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": thread_ts,
            "message_ts": message_ts,
            "conversation_id": conversation_id,
            "event_type": "user_message",
        },
    )

    # Record metrics
    _record_message_metrics(user_id, channel, text, conversation_id, thread_ts)

    thinking_message_ts = None

    try:
        # Process file attachments (Slack-specific)
        document_content, document_filename = await _process_and_cache_files(
            files, slack_service, conversation_cache, thread_ts
        )

        # Determine RAG setting based on thread type (Slack-specific)
        use_rag = await _determine_rag_setting(
            thread_ts, conversation_cache, document_filename
        )

        # Get user's custom system prompt (Slack-specific)
        system_message = get_user_system_prompt(user_id)

        # Get thread history (Slack-specific)
        history, should_use_thread_context = await slack_service.get_thread_history(
            channel, thread_ts
        )

        if should_use_thread_context:
            logger.info(
                f"Using thread context with {len(history)} messages for response generation"
            )

        # Send thinking indicator (Slack-specific)
        try:
            thinking_message_ts = await slack_service.send_thinking_indicator(
                channel, thread_ts
            )
        except Exception as e:
            logger.error(f"Error posting thinking message: {e}")

        # ===================================================================
        # CALL RAG-SERVICE - This handles ALL the intelligence:
        # - Agent routing (decides if query needs specialized agent)
        # - RAG retrieval (vector search for context)
        # - LLM generation (with tools like web search)
        # - Response generation with citations
        # ===================================================================

        rag_client = get_rag_client()
        result = await rag_client.generate_response(
            query=text,
            conversation_history=history,
            system_message=system_message,
            user_id=user_id,
            conversation_id=conversation_id,
            use_rag=use_rag,
            document_content=document_content,
            document_filename=document_filename,
            session_id=thread_ts,
        )

        response = result.get("response", "")
        # citations = result.get("citations", [])  # TODO: Format citations for Slack
        # metadata = result.get("metadata", {})

        # Clean up thinking message (Slack-specific)
        if thinking_message_ts:
            with contextlib.suppress(Exception):
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )
            thinking_message_ts = None

        # Format and send response (Slack-specific)
        if response:
            formatted_response = await MessageFormatter.format_message(response)
            await slack_service.send_message(
                channel=channel, text=formatted_response, thread_ts=thread_ts
            )
        else:
            response = (
                "I apologize, but I couldn't generate a response. Please try again."
            )
            await slack_service.send_message(
                channel=channel, text=response, thread_ts=thread_ts
            )

        # Trace conversation to Langfuse
        langfuse_service = get_langfuse_service()
        if langfuse_service:
            try:
                langfuse_service.trace_conversation(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=text,
                    bot_response=response,
                )
            except Exception as e:
                logger.warning(f"Error tracing conversation turn to Langfuse: {e}")

        # Record request timing
        metrics_service = get_metrics_service()
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

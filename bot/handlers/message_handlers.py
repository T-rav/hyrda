"""Core message handlers for bot - orchestrates message processing.

This module has been refactored to separate concerns:
- File processing → handlers/file_processors/
- Prompt management → handlers/prompt_manager.py
- Agent processes → handlers/agent_processes.py (existing)

Main responsibilities:
- Conversation ID management
- Message routing (agents vs LLM)
- Document caching
- RAG control
- Response formatting
"""

import contextlib
import logging
import time

from handlers.agent_processes import get_agent_blocks, run_agent_process
from handlers.file_processors import process_file_attachments
from services.agent_registry import get_agent_info, route_command
from services.formatting import MessageFormatter
from services.langfuse_service import get_langfuse_service
from services.llm_service import LLMService
from services.metrics_service import get_metrics_service
from services.slack_service import SlackService
from utils.errors import handle_error

logger = logging.getLogger(__name__)


# Thread tracking service (Redis-backed with in-memory fallback)
from services.thread_tracking import get_thread_tracking

_thread_tracking = get_thread_tracking()


# Helper functions for handle_message


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
    files: list[dict] | None,
    slack_service: SlackService,
    conversation_cache: object | None,
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


async def _add_document_reference_to_cache(
    document_content: str,
    conversation_cache: object | None,
    thread_ts: str | None,
    files: list[dict] | None,
) -> None:
    """Add document reference to conversation cache.

    Args:
        document_content: Document content string
        conversation_cache: Conversation cache instance
        thread_ts: Thread timestamp
        files: List of file attachments
    """
    if not (document_content and conversation_cache and thread_ts):
        return

    # Create concise summary instead of full content
    file_names = [f.get("name", "unknown") for f in files] if files else ["document"]
    file_summary = f"[User shared {len(file_names)} file(s): {', '.join(file_names)} - content processed and analyzed]"

    document_message = {"role": "user", "content": file_summary}
    await conversation_cache.update_conversation(
        thread_ts, document_message, is_bot_message=False
    )
    logger.info(
        f"Added document reference to conversation cache for thread {thread_ts}: {file_names}"
    )


async def _determine_rag_setting(
    thread_ts: str | None,
    conversation_cache: object | None,
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


async def _handle_agent_process_command(
    text: str,
    slack_service: SlackService,
    channel: str,
    thread_ts: str | None,
    user_id: str,
    conversation_id: str,
) -> bool:
    """Handle 'start <process>' commands.

    Args:
        text: Message text
        slack_service: Slack service instance
        channel: Slack channel ID
        thread_ts: Thread timestamp
        user_id: Slack user ID
        conversation_id: Unique conversation identifier

    Returns:
        True if command was handled, False otherwise
    """
    if not text.strip().lower().startswith("start "):
        return False

    agent_process_name = text.strip().lower()[6:]
    if not agent_process_name:
        return False

    logger.info(f"Starting agent process: {agent_process_name}")
    thinking_message_ts = None

    try:
        # Send thinking indicator
        thinking_message_ts = await slack_service.send_thinking_indicator(
            channel, thread_ts
        )

        # Run agent process
        result = await run_agent_process(process_id=agent_process_name)

        # Clean up thinking message
        if thinking_message_ts:
            try:
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )
                thinking_message_ts = None
            except Exception as e:
                logger.warning(f"Error deleting thinking message: {e}")

        # Send response
        response_text = result.data or "Process started"
        formatted_response = await MessageFormatter.format_message(response_text)
        agent_blocks = get_agent_blocks(result=result, user_id=user_id)

        await slack_service.send_message(
            channel=channel,
            text=formatted_response,
            blocks=agent_blocks,
            thread_ts=thread_ts,
        )

        # Trace to Langfuse
        langfuse_service = get_langfuse_service()
        if langfuse_service:
            try:
                langfuse_service.trace_conversation(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=text,
                    bot_response=response_text,
                )
            except Exception as e:
                logger.warning(f"Error tracing agent process turn to Langfuse: {e}")

        return True

    except Exception as e:
        # Clean up thinking message on error
        if thinking_message_ts:
            with contextlib.suppress(Exception):
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )

        logger.error(f"Agent process failed: {e}")
        error_response = f"❌ Agent process '{agent_process_name}' failed: {str(e)}"
        await slack_service.send_message(
            channel=channel, text=error_response, thread_ts=thread_ts
        )
        return True


async def _generate_and_send_llm_response(
    text: str,
    user_id: str,
    channel: str,
    thread_ts: str | None,
    slack_service: SlackService,
    llm_service: LLMService,
    conversation_id: str,
    conversation_cache: object | None,
    document_content: str,
    document_filename: str | None,
    use_rag: bool,
) -> str:
    """Generate LLM response and send to Slack.

    Args:
        text: User message text
        user_id: Slack user ID
        channel: Slack channel ID
        thread_ts: Thread timestamp
        slack_service: Slack service instance
        llm_service: LLM service instance
        conversation_id: Unique conversation identifier
        conversation_cache: Conversation cache instance
        document_content: Document content (if any)
        document_filename: Document filename (if any)
        use_rag: Whether to use RAG

    Returns:
        Generated response text
    """
    thinking_message_ts = None

    try:
        # Send thinking indicator
        thinking_message_ts = await slack_service.send_thinking_indicator(
            channel, thread_ts
        )
    except Exception as e:
        logger.error(f"Error posting thinking message: {e}")

    # Get thread history
    history, should_use_thread_context = await slack_service.get_thread_history(
        channel, thread_ts
    )

    if should_use_thread_context:
        logger.info(
            f"Using thread context with {len(history)} messages for response generation"
        )

    # Generate response
    response = await llm_service.get_response(
        messages=history,
        user_id=user_id,
        current_query=text,
        document_content=document_content if document_content else None,
        document_filename=document_filename,
        conversation_id=conversation_id,
        conversation_cache=conversation_cache,
        use_rag=use_rag,
    )

    # Clean up thinking message
    if thinking_message_ts:
        try:
            await slack_service.delete_thinking_indicator(channel, thinking_message_ts)
        except Exception as e:
            logger.warning(f"Error deleting thinking message: {e}")

    # Send response
    if response:
        formatted_response = await MessageFormatter.format_message(response)
        await slack_service.send_message(
            channel=channel, text=formatted_response, thread_ts=thread_ts
        )
    else:
        response = "I apologize, but I couldn't generate a response. Please try again."
        await slack_service.send_message(
            channel=channel, text=response, thread_ts=thread_ts
        )

    return response or ""


async def handle_bot_command(
    text: str,
    user_id: str,
    slack_service: SlackService,
    channel: str,
    thread_ts: str | None = None,
    files: list[dict] | None = None,
    document_content: str | None = None,
    llm_service: LLMService | None = None,
    check_thread_context: bool = False,
    conversation_cache: object | None = None,
    conversation_id: str | None = None,
) -> bool:
    """
    Handle bot agent commands using router pattern.

    Routes commands like /profile and /meddic to registered agents.
    Supports thread continuity - once an agent starts a thread, subsequent
    messages in that thread automatically route to the same agent.

    Args:
        text: Full message text (e.g., "/profile tell me about Charlotte")
        user_id: Slack user ID
        slack_service: Slack service for sending messages
        channel: Channel ID
        thread_ts: Thread timestamp if in a thread
        files: Optional list of file attachments
        document_content: Optional processed file content
        llm_service: Optional LLM service for agent use
        check_thread_context: If True, check if thread belongs to an agent

    Returns:
        True if bot command was handled, False otherwise
    """
    # Debug: Log what text we're receiving
    logger.info(
        f"handle_bot_command called with text: '{text}', check_thread_context: {check_thread_context}"
    )

    # Check for exit commands to clear thread tracking
    exit_commands = ["exit", "stop", "done", "end", "clear"]
    if thread_ts and any(text.strip().lower() == cmd for cmd in exit_commands):
        if await _thread_tracking.clear_thread(thread_ts):
            # Send confirmation
            try:
                await slack_service.send_message(
                    channel=channel,
                    text="✅ Exited agent mode. I'm back to general mode!",
                    thread_ts=thread_ts,
                )
            except Exception as e:
                logger.warning(f"Failed to send exit confirmation: {e}")
            return True
        # Not tracked, but return False to let it fall through
        return False

    # Check if this thread already belongs to an agent
    agent_name = (
        await _thread_tracking.get_thread_agent(thread_ts)
        if check_thread_context and thread_ts
        else None
    )
    if agent_name:
        logger.info(
            f"🔗 Thread {thread_ts} belongs to agent '{agent_name}' - routing automatically"
        )

        # Get agent info from registry
        agent_info = get_agent_info(agent_name)
        if agent_info:
            primary_name = agent_name
            query = text  # Use full text as query (no command prefix needed)
        else:
            logger.warning(
                f"Agent '{agent_name}' not found in registry, falling back to normal routing"
            )
            agent_info = None
            primary_name = None
            query = ""
    else:
        # Strip Slack markdown formatting (bold, italic, etc.) before routing
        # Slack sends *bold* and _italic_ which breaks command parsing
        clean_text = text.strip()
        # Remove leading/trailing markdown characters
        while clean_text and clean_text[0] in ["*", "_", "~"]:
            clean_text = clean_text[1:]
        while clean_text and clean_text[-1] in ["*", "_", "~"]:
            clean_text = clean_text[:-1]

        logger.info(f"Cleaned text for routing: '{clean_text}'")

        # Use router to parse and route command
        agent_info, query, primary_name = route_command(clean_text)

    # Debug: Log router results
    logger.info(
        f"Router results: agent_info={agent_info is not None}, primary_name={primary_name}, query='{query}'"
    )

    # If no agent found, return False (not handled)
    if not agent_info or not primary_name:
        logger.info("No agent found, returning False")
        return False

    logger.info(f"Routing to agent '{primary_name}' with query: {query}")

    # Send thinking indicator
    thinking_message_ts = None
    try:
        thinking_message_ts = await slack_service.send_thinking_indicator(
            channel, thread_ts
        )
    except Exception as e:
        logger.error(f"Error posting thinking message: {e}")

    try:
        # Build context for agent
        context = {
            "user_id": user_id,
            "channel": channel,
            "thread_ts": thread_ts,
            "thinking_ts": thinking_message_ts,  # Pass thinking indicator timestamp
            "slack_service": slack_service,
            "llm_service": llm_service,
            "conversation_cache": conversation_cache,  # For caching agent-generated docs
        }

        # Add file information if available
        if document_content:
            context["document_content"] = document_content
        if files:
            context["files"] = files
            context["file_names"] = [f.get("name", "unknown") for f in files]

        # Check permissions before execution
        from services.permission_service import get_permission_service

        permission_service = get_permission_service()
        allowed, reason = permission_service.can_use_agent(user_id, primary_name)

        if not allowed:
            # Permission denied - don't execute agent
            logger.warning(
                f"Permission denied: user {user_id} tried to use agent {primary_name}: {reason}"
            )

            # Clean up thinking message
            if thinking_message_ts:
                try:
                    await slack_service.delete_thinking_indicator(
                        channel, thinking_message_ts
                    )
                except Exception as e:
                    logger.warning(f"Error deleting thinking message: {e}")

            # Send permission denied message
            await slack_service.send_message(
                channel=channel,
                text=f"🔒 *Access Denied*\n\n{reason}\n\nContact an administrator if you need access to this agent.",
                thread_ts=thread_ts,
            )
            return True  # Command handled (but denied)

        # Permission granted - execute agent via agent-service
        logger.info(f"Permission granted: user {user_id} can use agent {primary_name}")
        from services.agent_client import get_agent_client

        agent_client = get_agent_client()
        result = await agent_client.invoke_agent(primary_name, query, context)
        response = result.get("response", "No response from agent")
        metadata = result.get("metadata", {})

        # Track this thread for future continuity (if we have a thread_ts)
        # Agent tracking and LangGraph checkpointing use SAME thread_id (thread_ts)
        # But allow agents to opt-out of tracking via metadata
        if thread_ts and primary_name:
            # Check if agent wants to auto-clear after completion
            if metadata.get("clear_thread_tracking", False):
                await _thread_tracking.clear_thread(thread_ts)
                logger.info(
                    f"🔓 Cleared both agent tracking AND LangGraph checkpoint for thread {thread_ts}"
                )
            else:
                await _thread_tracking.track_thread(thread_ts, primary_name)
                logger.info(
                    f"📌 Thread {thread_ts} tracked for agent '{primary_name}' (both Redis + LangGraph checkpoint)"
                )

        # Clean up thinking message
        if thinking_message_ts:
            try:
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )
            except Exception as e:
                logger.warning(f"Error deleting thinking message: {e}")

        # Format and send response (only if non-empty)
        # Agent may return empty response if it already posted the message (e.g., PDF upload with summary)
        if response:
            formatted_response = await MessageFormatter.format_message(response)
            await slack_service.send_message(
                channel=channel, text=formatted_response, thread_ts=thread_ts
            )
        else:
            logger.info("Agent returned empty response (likely already posted message)")

        # Record agent conversation turn in Langfuse for lifetime stats
        langfuse_service = get_langfuse_service()
        if langfuse_service and response:  # Only track if we have a response
            try:
                langfuse_service.trace_conversation(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=query,  # Agent query
                    bot_response=response or "",
                )
            except Exception as e:
                logger.warning(
                    f"Error tracing agent conversation turn to Langfuse: {e}"
                )

        return True

    except Exception as e:
        # Clean up thinking message on error
        if thinking_message_ts:
            with contextlib.suppress(Exception):
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )

        logger.error(f"Bot command '{primary_name}' failed: {e}")
        error_response = f"❌ Bot command '/{primary_name}' failed: {str(e)}"
        await slack_service.send_message(
            channel=channel, text=error_response, thread_ts=thread_ts
        )
        return True


async def handle_message(
    text: str,
    user_id: str,
    slack_service: SlackService,
    llm_service: LLMService,
    channel: str,
    thread_ts: str | None = None,
    files: list[dict] | None = None,
    conversation_cache: object | None = None,
    message_ts: str | None = None,
) -> None:
    """Handle an incoming message from Slack.

    Args:
        text: Message text
        user_id: Slack user ID
        slack_service: Slack service instance
        llm_service: LLM service instance
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

    try:
        # Process file attachments and retrieve cached documents
        document_content, document_filename = await _process_and_cache_files(
            files, slack_service, conversation_cache, thread_ts
        )

        # Check for bot agent commands (e.g., -profile, -meddic)
        handled = await handle_bot_command(
            text=text,
            user_id=user_id,
            slack_service=slack_service,
            channel=channel,
            thread_ts=thread_ts,
            files=files,
            document_content=document_content,
            llm_service=llm_service,
            check_thread_context=True,
            conversation_cache=conversation_cache,
            conversation_id=conversation_id,
        )

        if handled:
            return

        # Handle agent process commands (e.g., "start <process>")
        if await _handle_agent_process_command(
            text, slack_service, channel, thread_ts, user_id, conversation_id
        ):
            return

        # Add document reference to conversation cache
        await _add_document_reference_to_cache(
            document_content, conversation_cache, thread_ts, files
        )

        # Determine RAG setting based on thread type
        use_rag = await _determine_rag_setting(
            thread_ts, conversation_cache, document_filename
        )

        # Generate and send LLM response
        response = await _generate_and_send_llm_response(
            text=text,
            user_id=user_id,
            channel=channel,
            thread_ts=thread_ts,
            slack_service=slack_service,
            llm_service=llm_service,
            conversation_id=conversation_id,
            conversation_cache=conversation_cache,
            document_content=document_content,
            document_filename=document_filename,
            use_rag=use_rag,
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
        await handle_error(
            slack_service.client,
            channel,
            thread_ts,
            e,
            "I'm sorry, I encountered an error while processing your message.",
        )

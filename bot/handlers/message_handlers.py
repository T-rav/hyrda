import contextlib
import logging
import time
from io import BytesIO

import httpx

from handlers.file_processors import process_file_attachments
from services.formatting import MessageFormatter
from services.langfuse_service import get_langfuse_service
from services.llm_service import LLMService
from services.metrics_service import get_metrics_service
from services.prompt_service import get_prompt_service
from services.slack_service import SlackService
from utils.errors import handle_error

logger = logging.getLogger(__name__)


def get_user_system_prompt(user_id: str | None = None) -> str:
    """Get the system prompt with optional user context."""
    prompt_service = get_prompt_service()
    base_prompt = ""

    if prompt_service:
        base_prompt = prompt_service.get_system_prompt()
    else:
        logger.warning("PromptService not available, using minimal fallback prompt")
        base_prompt = "I'm Insight Mesh, your AI assistant. I help you find information from your organization's knowledge base and provide intelligent assistance with your questions."

    if user_id:
        try:
            from services.user_service import get_user_service

            user_service = get_user_service()
            user_info = user_service.get_user_info(user_id)

            if user_info:
                user_context = "\n\n**Current User Context:**\n"
                user_context += f"- Name: {user_info.get('real_name') or user_info.get('display_name', 'Unknown')}\n"
                if user_info.get("email_address"):
                    user_context += f"- Email: {user_info['email_address']}\n"

                user_context += "\nWhen responding, you can personalize your responses knowing who the user is. Address them by name when appropriate."

                return base_prompt + user_context
        except Exception as e:
            logger.error(f"Error injecting user context: {e}")

    return base_prompt


from services.thread_tracking import get_thread_tracking

_thread_tracking = get_thread_tracking()


async def _handle_exit_command(
    text: str, thread_ts: str | None, slack_service: SlackService, channel: str
) -> bool:
    """Handle exit commands to clear thread tracking."""
    exit_commands = ["exit", "stop", "done", "end", "clear"]
    if not thread_ts or not any(text.strip().lower() == cmd for cmd in exit_commands):
        return False

    if await _thread_tracking.clear_thread(thread_ts):
        try:
            await slack_service.send_message(
                channel=channel,
                text="✅ Exited agent mode. I'm back to general mode!",
                thread_ts=thread_ts,
            )
        except Exception as e:
            logger.warning(f"Failed to send exit confirmation: {e}")
        return True

    return False


async def _get_thread_agent(
    thread_ts: str | None, check_thread_context: bool
) -> str | None:
    """Get agent name associated with thread if context checking is enabled."""
    if not check_thread_context or not thread_ts:
        return None

    agent_name = await _thread_tracking.get_thread_agent(thread_ts)
    if agent_name:
        logger.info(
            f"🔗 Thread {thread_ts} belongs to agent '{agent_name}' - routing automatically"
        )
    return agent_name


def _clean_markdown_from_text(text: str) -> str:
    """Remove Slack markdown formatting from text."""
    clean_text = text.strip()
    while clean_text and clean_text[0] in ["*", "_", "~"]:
        clean_text = clean_text[1:]
    while clean_text and clean_text[-1] in ["*", "_", "~"]:
        clean_text = clean_text[:-1]
    return clean_text


async def _check_and_notify_unavailable_agent(
    text: str, slack_service: SlackService, channel: str, thread_ts: str | None
) -> bool:
    """Check if a disabled/unavailable agent was requested and notify user."""
    import re

    from services.agent_registry import check_agent_availability

    match = re.match(r"^[@-]?(\w+)[\s:].*", text.strip(), re.IGNORECASE)
    if not match:
        return False

    attempted_command = match.group(1).lower()
    logger.info(f"Extracted attempted command: '{attempted_command}'")

    availability = check_agent_availability(attempted_command)
    if not availability:
        return False

    error_msg = (
        f"❌ Agent `{attempted_command}` is not available.\n\n{availability['reason']}"
    )
    logger.info(
        f"Agent '{attempted_command}' exists but unavailable: {availability['reason']}"
    )

    try:
        await slack_service.send_message(
            channel=channel,
            text=error_msg,
            thread_ts=thread_ts,
        )
    except Exception as e:
        logger.error(f"Error sending unavailable agent message: {e}")

    return True


async def _execute_agent_with_streaming(
    primary_name: str,
    query: str,
    context: dict,
    slack_service: SlackService,
    channel: str,
    thread_ts: str | None,
) -> tuple[str, dict, str | None]:
    """Execute agent via HTTP with streaming status updates."""
    from services.agent_client import get_agent_client

    agent_client = get_agent_client()

    thinking_message_ts = None
    try:
        thinking_message_ts = await slack_service.send_thinking_indicator(
            channel, thread_ts
        )
    except Exception as e:
        logger.error(f"Error posting thinking message: {e}")

    logger.info(
        f"Streaming agent-service for '{primary_name}' with thread_id={context.get('thread_id')}"
    )

    response = ""
    metadata = {}
    all_steps = []

    async for event in agent_client.stream(primary_name, query, context):
        phase = event.get("phase")
        step = event.get("step")
        message = event.get("message")
        duration = event.get("duration")

        if phase and thinking_message_ts and step:
            if phase == "started":
                running_entry = f"⏳ {message}"
                if running_entry not in all_steps:
                    all_steps.append(running_entry)
            elif phase == "completed":
                running_entry = f"⏳ {message}"
                if running_entry in all_steps:
                    idx = all_steps.index(running_entry)
                    all_steps[idx] = f"✅ {message} ({duration})"
                else:
                    all_steps.append(f"✅ {message} ({duration})")

            status_text = (
                "\n".join(all_steps[-10:]) if all_steps else "⏳ Processing..."
            )

            logger.info(f"📊 Status update - Total steps: {len(all_steps)}")
            logger.info(f"📊 Status text:\n{status_text}")

            try:
                await slack_service.update_message(
                    channel, thinking_message_ts, status_text
                )
            except Exception as e:
                logger.warning(f"Failed to update status message: {e}")

        if event.get("type") == "result":
            data = event.get("data", {})
            if data.get("message"):
                response = data.get("message", "")
                if data.get("attachments"):
                    metadata["attachments"] = data.get("attachments")
                if data.get("followup_mode"):
                    metadata["followup_mode"] = data.get("followup_mode")
                logger.info(
                    f"Received result event with message ({len(response)} chars), "
                    f"{len(metadata.get('attachments', []))} attachment(s), "
                    f"followup_mode={metadata.get('followup_mode', False)}"
                )

                if thinking_message_ts:
                    final_status = "\n".join(all_steps[-10:]) + "\n\n✅ *Complete*"
                    try:
                        await slack_service.update_message(
                            channel, thinking_message_ts, final_status
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update final status: {e}")

        if "response" in event:
            response = event.get("response", "")
            metadata = event.get("metadata", {})

    return response, metadata, thinking_message_ts


async def _track_thread_for_continuity(
    thread_ts: str | None, primary_name: str | None, metadata: dict
) -> None:
    """Track thread for future continuity or clear if agent requests it."""
    if not thread_ts or not primary_name:
        return

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


async def _send_agent_response(
    response: str,
    thinking_message_ts: str | None,
    slack_service: SlackService,
    channel: str,
    thread_ts: str | None,
    user_id: str,
    query: str,
    conversation_id: str | None,
    metadata: dict | None = None,
) -> None:
    """Format and send agent response, track in Langfuse."""
    if response:
        formatted_response = await MessageFormatter.format_message(response)
        await slack_service.send_message(
            channel=channel, text=formatted_response, thread_ts=thread_ts
        )
    else:
        logger.info("Agent returned empty response (likely already posted message)")

    if metadata and metadata.get("attachments"):
        attachments = metadata.get("attachments", [])
        logger.info(f"Processing {len(attachments)} attachment(s)")

        for attachment in attachments:
            if not attachment.get("inject", False):
                continue

            url = attachment.get("url")
            filename = attachment.get("filename", "attachment.pdf")

            if not url:
                logger.warning(f"Attachment missing URL: {attachment}")
                continue

            try:
                logger.info(f"Downloading attachment from {url}")
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:  # nosec B501
                    file_response = await client.get(url)
                    file_response.raise_for_status()
                    file_content = BytesIO(file_response.content)

                logger.info(f"Uploading {filename} to Slack")
                await slack_service.upload_file(
                    channel=channel,
                    file_content=file_content,
                    filename=filename,
                    thread_ts=thread_ts,
                )
                logger.info(f"Successfully uploaded {filename}")

            except Exception as e:
                logger.error(f"Failed to process attachment {filename}: {e}")

    langfuse_service = get_langfuse_service()
    if langfuse_service and response:
        try:
            langfuse_service.trace_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=query,
                bot_response=response,
            )
        except Exception as e:
            logger.warning(f"Error tracing agent conversation turn to Langfuse: {e}")


def _determine_conversation_id(
    channel: str, thread_ts: str | None, message_ts: str | None
) -> str:
    """Determine unique conversation ID from Slack context."""
    is_dm = channel.startswith("D")

    if thread_ts:
        return thread_ts
    elif is_dm:
        return channel
    elif message_ts:
        return message_ts
    else:
        raise ValueError("Must provide thread_ts or message_ts for non-DM messages")


def _record_message_metrics(
    metrics_service,
    user_id: str,
    channel: str,
    text: str,
    conversation_id: str,
    thread_ts: str | None,
) -> None:
    """Record message processing metrics."""
    if not metrics_service:
        return

    metrics_service.record_message_processed(
        user_id=user_id, channel_type="dm" if channel.startswith("D") else "channel"
    )

    metrics_service.record_conversation_activity(conversation_id)

    query_category = "question"
    if text.lower().startswith(("run ", "execute ", "start ")):
        query_category = "command"
    elif thread_ts:
        query_category = "conversation"

    has_context = bool(thread_ts)
    metrics_service.record_query_type(query_category, has_context)


async def _get_or_store_document_content(
    conversation_cache,
    thread_ts: str | None,
    document_content: str,
    document_filename: str | None,
) -> tuple[str, str | None]:
    """Get cached document or store new one."""
    if not thread_ts or not conversation_cache:
        return document_content, document_filename

    if document_content:
        await conversation_cache.store_document_content(
            thread_ts, document_content, document_filename or "unknown"
        )
        return document_content, document_filename

    stored_content, stored_filename = await conversation_cache.get_document_content(
        thread_ts
    )
    if stored_content:
        logger.info(
            f"Retrieved previously stored document for thread {thread_ts}: {stored_filename}"
        )
        return stored_content, stored_filename

    return document_content, document_filename


async def _add_document_reference_to_cache(
    conversation_cache,
    thread_ts: str | None,
    document_content: str,
    files: list[dict] | None,
) -> None:
    """Add document reference summary to conversation cache."""
    if not (document_content and conversation_cache and thread_ts):
        return

    file_names = [f.get("name", "unknown") for f in files] if files else ["document"]
    file_summary = f"[User shared {len(file_names)} file(s): {', '.join(file_names)} - content processed and analyzed]"

    document_message = {
        "role": "user",
        "content": file_summary,
    }
    await conversation_cache.update_conversation(
        thread_ts, document_message, is_bot_message=False
    )
    logger.info(
        f"Added document reference to conversation cache for thread {thread_ts}: {file_names}"
    )


async def _determine_rag_usage(
    conversation_cache, thread_ts: str | None
) -> tuple[bool, str | None]:
    """Determine whether to use RAG based on thread type."""
    thread_type = None
    if thread_ts and conversation_cache:
        thread_type = await conversation_cache.get_thread_type(thread_ts)
        logger.info(
            f"Thread {thread_ts}: type={thread_type}, has_cache={conversation_cache is not None}"
        )

    is_profile_thread = thread_type == "profile"
    use_rag = not is_profile_thread

    if is_profile_thread:
        logger.info(f"✅ Disabling RAG for profile thread {thread_ts}")
    else:
        logger.info(
            f"📚 RAG enabled for thread {thread_ts} (thread_type={thread_type})"
        )

    return use_rag, thread_type


async def _send_llm_response(
    response: str,
    thinking_message_ts: str | None,
    slack_service: SlackService,
    channel: str,
    thread_ts: str | None,
    user_id: str,
    text: str,
    conversation_id: str,
) -> None:
    """Clean up thinking indicator and send formatted response."""
    if thinking_message_ts:
        try:
            await slack_service.delete_thinking_indicator(channel, thinking_message_ts)
        except Exception as e:
            logger.warning(f"Error deleting thinking message: {e}")

    if response:
        formatted_response = await MessageFormatter.format_message(response)
        await slack_service.send_message(
            channel=channel, text=formatted_response, thread_ts=thread_ts
        )
    else:
        response = "I apologize, but I couldn't generate a response. Please try again."
        await slack_service.send_message(
            channel=channel,
            text=response,
            thread_ts=thread_ts,
        )

    langfuse_service = get_langfuse_service()
    if langfuse_service:
        try:
            langfuse_service.trace_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=text,
                bot_response=response or "",
            )
        except Exception as e:
            logger.warning(f"Error tracing conversation turn to Langfuse: {e}")


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
    conversation_cache=None,
    conversation_id: str | None = None,
    trace_context: dict[str, str] | None = None,
) -> bool:
    """Handle bot agent commands using router pattern.

    Routes commands like /profile and /meddic to registered agents.
    Supports thread continuity - once an agent starts a thread, subsequent
    messages in that thread automatically route to the same agent.
    """
    logger.info(
        f"handle_bot_command called with text: '{text}', check_thread_context: {check_thread_context}"
    )

    if await _handle_exit_command(text, thread_ts, slack_service, channel):
        return True

    agent_name = await _get_thread_agent(thread_ts, check_thread_context)
    if agent_name:
        from services.agent_registry import get_agent_info

        agent_info = get_agent_info(agent_name)
        if agent_info:
            primary_name = agent_name
            query = text
        else:
            logger.warning(
                f"Agent '{agent_name}' not found in registry, falling back to normal routing"
            )
            agent_info = None
            primary_name = None
            query = ""
    else:
        clean_text = _clean_markdown_from_text(text)
        logger.info(f"Cleaned text for routing: '{clean_text}'")

        from services.agent_registry import route_command

        agent_info, query, primary_name = route_command(clean_text)

    logger.info(
        f"Router results: agent_info={agent_info is not None}, primary_name={primary_name}, query='{query}'"
    )

    if not agent_info or not primary_name:
        logger.info("No agent found in enabled registry, checking availability...")
        clean_text = _clean_markdown_from_text(text)
        if await _check_and_notify_unavailable_agent(
            clean_text, slack_service, channel, thread_ts
        ):
            return True

        logger.info("No agent found, returning False")
        return False

    logger.info(f"Routing to agent '{primary_name}' with query: {query}")

    thread_id = f"slack_{channel}_{thread_ts}" if thread_ts else f"slack_{channel}_dm"
    context = {
        "thread_id": thread_id,
        "user_id": user_id,
        "channel": channel,
        "thread_ts": thread_ts,
    }

    if trace_context:
        context["trace_context"] = trace_context
        logger.info(f"Added trace context to agent context: {trace_context}")

    if document_content:
        context["document_content"] = document_content
    if files:
        context["files"] = files
        context["file_names"] = [f.get("name", "unknown") for f in files]

    try:
        response, metadata, thinking_message_ts = await _execute_agent_with_streaming(
            primary_name, query, context, slack_service, channel, thread_ts
        )

        await _track_thread_for_continuity(thread_ts, primary_name, metadata)

        await _send_agent_response(
            response,
            thinking_message_ts,
            slack_service,
            channel,
            thread_ts,
            user_id,
            query,
            conversation_id,
            metadata,
        )

        return True

    except Exception as e:
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
    conversation_cache=None,
    message_ts: str | None = None,
):
    """Handle an incoming message from Slack."""
    start_time = time.time()

    conversation_id = _determine_conversation_id(channel, thread_ts, message_ts)

    is_dm = channel.startswith("D")

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

    metrics_service = get_metrics_service()
    _record_message_metrics(
        metrics_service, user_id, channel, text, conversation_id, thread_ts
    )

    langfuse_service = get_langfuse_service()
    root_trace_id = None
    root_obs_id = None
    if langfuse_service:
        root_trace_id, root_obs_id = langfuse_service.start_root_span(
            name="slack_message",
            input_data={
                "message": text,
                "user_id": user_id,
                "conversation_id": conversation_id,
            },
            metadata={
                "channel": channel,
                "is_dm": is_dm,
                "has_thread": bool(thread_ts),
                "has_files": bool(files),
            },
        )
        logger.debug(
            f"Started root trace for message: trace_id={root_trace_id}, obs_id={root_obs_id}"
        )

    thinking_message_ts = None

    try:
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

        trace_context = None
        if root_trace_id and root_obs_id:
            trace_context = {
                "trace_id": root_trace_id,
                "parent_span_id": root_obs_id,
            }

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
            trace_context=trace_context,
        )

        if handled:
            return

        try:
            thinking_message_ts = await slack_service.send_thinking_indicator(
                channel, thread_ts
            )
        except Exception as e:
            logger.error(f"Error posting thinking message: {e}")

        document_content, document_filename = await _get_or_store_document_content(
            conversation_cache, thread_ts, document_content, document_filename
        )

        history, should_use_thread_context = await slack_service.get_thread_history(
            channel, thread_ts
        )

        if should_use_thread_context:
            logger.info(
                f"Using thread context with {len(history)} messages for response generation"
            )

        await _add_document_reference_to_cache(
            conversation_cache, thread_ts, document_content, files
        )

        use_rag, thread_type = await _determine_rag_usage(conversation_cache, thread_ts)

        logger.info(
            f"Thread {thread_ts}: thread_type={thread_type}, use_rag={use_rag}, "
            f"has_document={document_content is not None}"
        )

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

        await _send_llm_response(
            response,
            thinking_message_ts,
            slack_service,
            channel,
            thread_ts,
            user_id,
            text,
            conversation_id,
        )

        if metrics_service:
            duration = time.time() - start_time
            metrics_service.request_duration.labels(
                endpoint="message_handler", method="POST"
            ).observe(duration)

    except Exception as e:
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

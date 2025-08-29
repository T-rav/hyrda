import logging
from datetime import datetime

from handlers.agent_processes import get_agent_blocks, run_agent_process
from services.formatting import MessageFormatter
from services.llm_service import LLMService
from services.slack_service import SlackService
from services.user_prompt_service import UserPromptService
from utils.errors import handle_error

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_MESSAGE = """You are a helpful assistant for Insight Mesh, a RAG (Retrieval-Augmented Generation) system. You help users understand and work with their data. You can also start agent processes on behalf of users when you request it."""

# Constants
PROMPT_PREVIEW_LENGTH = 100
HTTP_OK = 200

PROMPT_HELP_TEXT = """**@prompt Commands:**

• `@prompt` - Show this help message
• `@prompt <your custom prompt>` - Set a new system prompt
• `@prompt history` - Show your last 5 system prompts
• `@prompt reset` - Reset to default system prompt

**Examples:**
• `@prompt You are a Python expert who gives concise code examples`
• `@prompt You are a helpful SQL assistant`"""


async def get_user_system_prompt(
    user_id: str, prompt_service: UserPromptService
) -> str:
    """Get the current system prompt for a user, or default if none set"""
    if not prompt_service:
        return DEFAULT_SYSTEM_MESSAGE

    prompt = await prompt_service.get_user_prompt(user_id)
    return prompt if prompt else DEFAULT_SYSTEM_MESSAGE


async def handle_prompt_command(
    text: str,
    user_id: str,
    slack_service: SlackService,
    channel: str,
    thread_ts: str | None = None,
    prompt_service: UserPromptService | None = None,
) -> bool:
    """Handle @prompt commands. Returns True if command was handled."""
    text = text.strip()

    # Check if this is a @prompt command
    if not text.startswith("@prompt"):
        return False

    # Extract the command part
    command_part = text[7:].strip()  # Remove "@prompt"

    # Handle different @prompt commands
    if not command_part:
        # Just "@prompt" - show help
        await slack_service.send_message(
            channel=channel, text=PROMPT_HELP_TEXT, thread_ts=thread_ts
        )
        return True

    elif command_part.lower() == "history":
        # Show user's prompt history
        if not prompt_service:
            response = "Database not available. History feature disabled."
        else:
            history = await prompt_service.get_user_prompt_history(user_id)
            if not history:
                response = "You haven't set any custom system prompts yet. Use `@prompt <your prompt>` to set one."
            else:
                response = "**Your Recent System Prompts:**\n\n"
                for i, entry in enumerate(history, 1):
                    timestamp = datetime.fromisoformat(
                        entry["timestamp"].replace("Z", "+00:00")
                    )
                    formatted_time = timestamp.strftime("%m/%d %H:%M")
                    current_indicator = " *(current)*" if entry["is_current"] else ""
                    response += f"{i}. *{formatted_time}* - {entry['preview']}{current_indicator}\n"

        await slack_service.send_message(
            channel=channel, text=response, thread_ts=thread_ts
        )
        return True

    elif command_part.lower() == "reset":
        # Reset to default prompt
        if not prompt_service:
            response = "Database not available. Reset feature disabled."
        else:
            await prompt_service.reset_user_prompt(user_id)
            response = "✅ System prompt reset to default."

        await slack_service.send_message(
            channel=channel, text=response, thread_ts=thread_ts
        )
        return True

    else:
        # Set new system prompt
        if not prompt_service:
            response = "Database not available. Custom prompts disabled."
        else:
            new_prompt = command_part
            await prompt_service.set_user_prompt(user_id, new_prompt)

            preview = (
                new_prompt[:PROMPT_PREVIEW_LENGTH] + "..."
                if len(new_prompt) > PROMPT_PREVIEW_LENGTH
                else new_prompt
            )
            response = f"✅ **System prompt updated:**\n\n{preview}"

        await slack_service.send_message(
            channel=channel, text=response, thread_ts=thread_ts
        )
        return True


async def handle_message(
    text: str,
    user_id: str,
    slack_service: SlackService,
    llm_service: LLMService,
    channel: str,
    thread_ts: str | None = None,
    conversation_cache=None,
    prompt_service: UserPromptService | None = None,
):
    """Handle an incoming message from Slack"""
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

    # For tracking the thinking indicator message
    thinking_message_ts = None

    try:
        # Check if this is a @prompt command first
        if await handle_prompt_command(
            text, user_id, slack_service, channel, thread_ts, prompt_service
        ):
            return  # Command handled, no need for LLM response

        # Log thread info
        if thread_ts:
            logger.info(f"Responding in existing thread: {thread_ts}")
        else:
            logger.info("Starting a new thread")

        # Post a thinking message (we'll delete this later)
        thinking_message_ts = await slack_service.send_thinking_indicator(
            channel, thread_ts
        )

        # Retrieve thread history if this is a message in a thread
        thread_messages = []
        cache_source = "none"
        if thread_ts and thread_ts != "None":
            if conversation_cache:
                (
                    thread_messages,
                    success,
                    cache_source,
                ) = await conversation_cache.get_conversation(
                    channel, thread_ts, slack_service
                )
            else:
                thread_messages, success = await slack_service.get_thread_history(
                    channel, thread_ts
                )
                cache_source = "slack_api"

        # Prepare the LLM request
        llm_messages = await prepare_llm_messages(
            text, thread_messages, user_id, prompt_service
        )

        # Log the full context being sent to LLM
        logger.debug(
            "Sending context to LLM",
            extra={
                "llm_messages": llm_messages,
                "user_id": user_id,
                "channel_id": channel,
                "thread_ts": thread_ts,
                "event_type": "llm_request",
                "message_count": len(llm_messages),
                "cache_source": cache_source,
            },
        )

        # Get the LLM response
        conversation_id = (
            thread_ts or f"{channel}_{user_id}"
        )  # Use thread_ts or fallback
        llm_response = await llm_service.get_response(
            messages=llm_messages, user_id=user_id, conversation_id=conversation_id
        )

        # Delete the thinking message
        await slack_service.delete_thinking_indicator(channel, thinking_message_ts)
        thinking_message_ts = None

        # Send the response
        if llm_response:
            logger.info(
                "Generated LLM response",
                extra={
                    "llm_response": llm_response,
                    "user_id": user_id,
                    "channel_id": channel,
                    "thread_ts": thread_ts,
                    "event_type": "llm_response",
                    "response_length": len(llm_response),
                },
            )

            # Format the response for better rendering in Slack
            formatted_response = await MessageFormatter.format_message(llm_response)

            await slack_service.send_message(
                channel=channel, text=formatted_response, thread_ts=thread_ts
            )

            logger.info(
                "Response sent to Slack",
                extra={
                    "user_id": user_id,
                    "channel_id": channel,
                    "thread_ts": thread_ts,
                    "event_type": "slack_response_sent",
                    "formatted_response": formatted_response,
                },
            )

            # Update conversation cache with user message and bot response
            if conversation_cache and thread_ts:
                # Add user message to cache
                await conversation_cache.update_conversation(
                    thread_ts, {"role": "user", "content": text}, is_bot_message=False
                )
                # Add bot response to cache
                await conversation_cache.update_conversation(
                    thread_ts,
                    {"role": "assistant", "content": llm_response},
                    is_bot_message=True,
                )
        else:
            logger.error(
                "No LLM response received",
                extra={
                    "user_id": user_id,
                    "channel_id": channel,
                    "thread_ts": thread_ts,
                    "event_type": "llm_response_failed",
                },
            )
            await slack_service.send_message(
                channel=channel,
                text="I'm sorry, I encountered an error while generating a response.",
                thread_ts=thread_ts,
            )

    except Exception as e:
        # Handle any errors
        await handle_error(
            slack_service.client,
            channel,
            thread_ts,
            e,
            "I'm sorry, something went wrong. Please try again later.",
        )

        # Delete the thinking message if there was an error
        if thinking_message_ts:
            await slack_service.delete_thinking_indicator(channel, thinking_message_ts)


async def prepare_llm_messages(
    text: str,
    thread_messages: list[dict[str, str]],
    user_id: str,
    prompt_service: UserPromptService | None = None,
) -> list[dict[str, str]]:
    """Prepare messages for the LLM API call"""
    # Start with user-specific system message
    system_prompt = await get_user_system_prompt(user_id, prompt_service)
    messages = [
        {"role": "system", "content": system_prompt},
    ]

    # Add thread history if available
    if thread_messages:
        messages.extend(thread_messages)
        logger.info("Added thread history to context")

    # Add current message if it's not already included in thread history
    if text and (not thread_messages or thread_messages[-1]["content"] != text):
        messages.append({"role": "user", "content": text})

    logger.info(f"Prepared {len(messages)} messages for LLM API")
    return messages


async def handle_agent_action(
    action_id: str,
    user_id: str,
    slack_service: SlackService,
    channel: str,
    thread_ts: str,
):
    """Handle agent process actions"""
    logger.info(f"Handling agent action: {action_id}")

    # Show thinking indicator
    thinking_message = await slack_service.send_thinking_indicator(channel, thread_ts)

    # Run the agent process
    result = await run_agent_process(action_id)

    # Delete thinking message
    await slack_service.delete_thinking_indicator(channel, thinking_message)

    # Create a rich message with process info
    blocks = get_agent_blocks(result, user_id)

    # Determine the fallback text based on success
    text = (
        f"Agent process {result.get('name', action_id)} started successfully."
        if result.get("success")
        else f"Failed to start agent process: {result.get('error', 'Unknown error')}"
    )

    # Send the response
    await slack_service.send_message(
        channel=channel, text=text, thread_ts=thread_ts, blocks=blocks
    )

import contextlib
import logging

from handlers.agent_processes import get_agent_blocks, run_agent_process
from services.formatting import MessageFormatter
from services.llm_service import LLMService
from services.slack_service import SlackService
from utils.errors import handle_error

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_MESSAGE = """You are a helpful assistant for Insight Mesh, a RAG (Retrieval-Augmented Generation) system. You help users understand and work with their data. You can also start agent processes on behalf of users when you request it."""

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
    conversation_cache=None,
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
        # Show typing indicator
        try:
            await slack_service.post_typing(channel)
        except Exception as e:
            logger.warning(f"Error posting typing indicator: {e}")

        # Handle agent process commands
        if text.strip().lower().startswith("start "):
            agent_process_name = text.strip().lower()[6:]
            if agent_process_name:
                logger.info(f"Starting agent process: {agent_process_name}")

                try:
                    # First send thinking message
                    thinking_message_ts = await slack_service.post_thinking_message(
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
                            await slack_service.delete_message(
                                channel, thinking_message_ts
                            )
                            thinking_message_ts = None
                        except Exception as e:
                            logger.warning(f"Error deleting thinking message: {e}")

                    # Send response with agent blocks
                    formatted_response = MessageFormatter.format_response(response)
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
                            await slack_service.delete_message(
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
            thinking_message_ts = await slack_service.post_thinking_message(
                channel, thread_ts
            )
        except Exception as e:
            logger.error(f"Error posting thinking message: {e}")

        # Get the thread history for context
        history, should_use_thread_context = await slack_service.get_thread_history(
            channel, thread_ts
        )

        if should_use_thread_context:
            logger.info(
                f"Using thread context with {len(history)} messages for response generation"
            )

        # Generate response using LLM service
        response = await llm_service.get_response(
            messages=history,
            user_id=user_id,
        )

        # Clean up thinking message
        if thinking_message_ts:
            try:
                await slack_service.delete_message(channel, thinking_message_ts)
            except Exception as e:
                logger.warning(f"Error deleting thinking message: {e}")

        # Format and send the response
        if response:
            formatted_response = MessageFormatter.format_response(response)
            await slack_service.send_message(
                channel=channel, text=formatted_response, thread_ts=thread_ts
            )
        else:
            await slack_service.send_message(
                channel=channel,
                text="I apologize, but I couldn't generate a response. Please try again.",
                thread_ts=thread_ts,
            )

    except Exception as e:
        # Clean up thinking message on error
        if thinking_message_ts:
            with contextlib.suppress(Exception):
                await slack_service.delete_message(channel, thinking_message_ts)

        await handle_error(
            slack_service.client,
            channel,
            thread_ts,
            e,
            "I'm sorry, I encountered an error while processing your message.",
        )

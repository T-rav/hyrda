import logging
import traceback

from handlers.message_handlers import handle_message
from services.llm_service import LLMService
from services.slack_service import SlackService
from utils.errors import handle_error

logger = logging.getLogger(__name__)


async def register_handlers(app, slack_service, llm_service, conversation_cache=None):
    """Register all event handlers with the Slack app"""

    @app.event("assistant_thread_started")
    async def handle_assistant_thread_started(body, client):
        """Handle the event when a user starts an AI assistant thread"""
        logger.info("Assistant thread started")
        try:
            event = body["event"]
            channel_id = event["channel"]
            thread_ts = event.get("thread_ts")
            # User ID not currently used but available for future features
            _user_id = event.get("user")

            # Send a welcome message
            await slack_service.send_message(
                channel=channel_id,
                text="👋 Hello! I'm Insight Mesh Assistant. I can help answer questions about your data or start agent processes for you.",
                thread_ts=thread_ts,
            )
        except Exception as e:
            logger.error(f"Error handling assistant thread started: {e}")

    @app.event("app_mention")
    async def handle_mention(body, client):
        """Handle when the bot is mentioned in a channel"""
        logger.info("Received app mention")
        try:
            event = body["event"]
            user_id = event["user"]
            text = event["text"]
            text = (
                text.split("<@", 1)[-1].split(">", 1)[-1].strip()
                if ">" in text
                else text
            )
            channel = event["channel"]

            # Always use the original message timestamp as thread_ts if not already in a thread
            thread_ts = event.get("thread_ts", event.get("ts"))

            logger.info(
                f"Handling mention in channel {channel}, thread {thread_ts}, text: '{text}'"
            )

            await handle_message(
                text=text,
                user_id=user_id,
                slack_service=slack_service,
                llm_service=llm_service,
                channel=channel,
                thread_ts=thread_ts,
                conversation_cache=conversation_cache,
            )
        except Exception as e:
            await handle_error(
                client,
                body["event"]["channel"],
                body["event"].get("thread_ts", body["event"].get("ts")),
                e,
                "I'm sorry, I encountered an error while processing your request.",
            )

    @app.event({"type": "message", "subtype": None})
    @app.event("message")
    async def handle_message_event(body, client):
        """Handle all message events including those in threads"""
        logger.info("Received message event")
        try:
            event = body["event"]

            # Log key message details
            logger.debug(
                f"Message event: channel={event.get('channel')}, user={event.get('user')}, thread_ts={event.get('thread_ts')}"
            )

            # Skip if it's from a bot
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                logger.info("Skipping bot message")
                return

            user_id = event.get("user")
            if not user_id:
                logger.info("Skipping message with no user")
                return

            channel = event.get("channel")
            channel_type = event.get("channel_type", "")
            text = event.get("text", "").strip()
            thread_ts = event.get("thread_ts")
            ts = event.get("ts")

            logger.debug(
                f"Processing message: channel_type={channel_type}, thread_ts={thread_ts}, text='{text}'"
            )

            # Process message based on context
            await process_message_by_context(
                user_id=user_id,
                channel=channel,
                channel_type=channel_type,
                text=text,
                thread_ts=thread_ts,
                ts=ts,
                slack_service=slack_service,
                llm_service=llm_service,
                conversation_cache=conversation_cache,
            )

        except Exception as e:
            logger.error(f"Error in message event handler: {e}")

            logger.error(f"Message handler error: {traceback.format_exc()}")


async def process_message_by_context(
    user_id: str,
    channel: str,
    channel_type: str,
    text: str,
    thread_ts: str | None,
    ts: str,
    slack_service: SlackService,
    llm_service: LLMService,
    conversation_cache=None,
):
    """Process message based on its context (DM, mention, thread)"""

    logger.debug(
        f"Processing message: channel_type={channel_type}, thread_ts={thread_ts}"
    )

    # Check if message is in a DM
    if channel_type == "im":
        logger.info("Processing DM message")
        await handle_message(
            text=text,
            user_id=user_id,
            slack_service=slack_service,
            llm_service=llm_service,
            channel=channel,
            thread_ts=thread_ts or ts,  # Use thread_ts if in thread, otherwise ts
            conversation_cache=conversation_cache,
        )
        return

    # Check if message mentions the bot (in any context)
    bot_id = slack_service.bot_id
    is_mention = f"<@{bot_id}>" in text if bot_id else False

    if is_mention:
        logger.info("Processing message with bot mention")
        # Extract text after mention
        clean_text = text.split(">", 1)[-1].strip() if ">" in text else text
        await handle_message(
            text=clean_text,
            user_id=user_id,
            slack_service=slack_service,
            llm_service=llm_service,
            channel=channel,
            thread_ts=thread_ts or ts,
            conversation_cache=conversation_cache,
        )
        return

    # If in thread, check if bot should respond
    if thread_ts:
        logger.info("Message is in a thread, checking participation")

        try:
            # Check if bot is already a participant in this thread
            thread_info = await slack_service.get_thread_info(channel, thread_ts)

            # Only respond if the bot is already a participant in this thread
            if thread_info.get("bot_is_participant", False):
                logger.info("Bot responding to thread message")
                await handle_message(
                    text=text,
                    user_id=user_id,
                    slack_service=slack_service,
                    llm_service=llm_service,
                    channel=channel,
                    thread_ts=thread_ts,
                    conversation_cache=conversation_cache,
                )
            else:
                logger.debug("Bot is not a participant in this thread, ignoring")
        except Exception as e:
            logger.error(f"Error checking thread history: {e}")
            # On permission errors, respond anyway since we can't verify participation
            await handle_message(
                text=text,
                user_id=user_id,
                slack_service=slack_service,
                llm_service=llm_service,
                channel=channel,
                thread_ts=thread_ts,
                conversation_cache=conversation_cache,
            )
        return

    logger.info("Message doesn't meet criteria for bot response, ignoring")

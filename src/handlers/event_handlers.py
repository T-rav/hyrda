import logging
import re
from typing import Optional

from handlers.message_handlers import handle_message, handle_agent_action
from services.llm_service import LLMService
from services.slack_service import SlackService
from utils.errors import handle_error

logger = logging.getLogger(__name__)

async def register_handlers(app, slack_service, llm_service):
    """Register all event handlers with the Slack app"""
    
    @app.event("assistant_thread_started")
    async def handle_assistant_thread_started(body, client):
        """Handle the event when a user starts an AI assistant thread"""
        logger.info("Assistant thread started")
        try:
            event = body["event"]
            channel_id = event["channel"]
            thread_ts = event.get("thread_ts")
            user_id = event.get("user")
            
            # Send a welcome message
            await slack_service.send_message(
                channel=channel_id,
                text="👋 Hello! I'm Insight Mesh Assistant. I can help answer questions about your data or start agent processes for you.",
                thread_ts=thread_ts
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
            text = text.split("<@", 1)[-1].split(">", 1)[-1].strip() if ">" in text else text
            channel = event["channel"]
            
            # Always use the original message timestamp as thread_ts if not already in a thread
            thread_ts = event.get("thread_ts", event.get("ts"))
            
            logger.info(f"Handling mention in channel {channel}, thread {thread_ts}, text: '{text}'")
            
            await handle_message(
                text=text,
                user_id=user_id,
                slack_service=slack_service,
                llm_service=llm_service,
                channel=channel,
                thread_ts=thread_ts
            )
        except Exception as e:
            await handle_error(
                client,
                body["event"]["channel"],
                body["event"].get("thread_ts", body["event"].get("ts")),
                e,
                "I'm sorry, I encountered an error while processing your request."
            )

    @app.event({"type": "message", "subtype": None})
    @app.event("message")
    async def handle_message_event(body, client):
        """Handle all message events including those in threads"""
        logger.info("Received message event")
        try:
            event = body["event"]
            
            # Enhanced logging for ALL incoming messages
            logger.info(f"FULL MESSAGE EVENT: {event}")
            logger.info(f"Event keys: {list(event.keys())}")
            logger.info(f"Channel type: {event.get('channel_type', 'N/A')}")
            logger.info(f"User ID: {event.get('user', 'MISSING')}")
            logger.info(f"Bot ID: {event.get('bot_id', 'N/A')}")
            logger.info(f"Subtype: {event.get('subtype', 'N/A')}")
            logger.info(f"Thread TS: {event.get('thread_ts', 'N/A')}")
            logger.info(f"TS: {event.get('ts', 'N/A')}")
            logger.info(f"Text: '{event.get('text', '')}'")
            
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
            
            logger.debug(f"Processing message: channel_type={channel_type}, thread_ts={thread_ts}, text='{text}'")
            
            # Process message based on context
            await process_message_by_context(
                user_id=user_id,
                channel=channel,
                channel_type=channel_type,
                text=text,
                thread_ts=thread_ts,
                ts=ts,
                slack_service=slack_service,
                llm_service=llm_service
            )
                
        except Exception as e:
            logger.error(f"Error in message event handler: {e}")
            import traceback
            logger.error(f"Message handler error: {traceback.format_exc()}")

async def process_message_by_context(
    user_id: str,
    channel: str,
    channel_type: str,
    text: str,
    thread_ts: Optional[str],
    ts: str,
    slack_service: SlackService,
    llm_service: LLMService
):
    """Process message based on its context (DM, mention, thread)"""
    
    logger.info(f"CONTEXT DECISION - user_id: {user_id}, channel: {channel}, channel_type: {channel_type}")
    logger.info(f"CONTEXT DECISION - thread_ts: {thread_ts}, ts: {ts}")
    
    # Check if message is in a DM
    if channel_type == "im":
        logger.info("Processing DM message")
        await handle_message(
            text=text,
            user_id=user_id,
            slack_service=slack_service,
            llm_service=llm_service,
            channel=channel,
            thread_ts=thread_ts or ts  # Use thread_ts if in thread, otherwise ts
        )
        return
        
    # Check if message mentions the bot (in any context)
    bot_id = slack_service.bot_id
    is_mention = f"<@{bot_id}>" in text if bot_id else False
    
    if is_mention:
        logger.info(f"Processing message with bot mention - bot_id: {bot_id}, is_mention: {is_mention}")
        # Extract text after mention
        clean_text = text.split(">", 1)[-1].strip() if ">" in text else text
        await handle_message(
            text=clean_text,
            user_id=user_id,
            slack_service=slack_service,
            llm_service=llm_service,
            channel=channel,
            thread_ts=thread_ts or ts
        )
        return
        
    # If in thread, respond to all messages in the thread
    if thread_ts:
        logger.info(f"Message is in a thread, processing - thread_ts: {thread_ts}")
        
        try:
            # IMPORTANT: FORCE RESPONSE IN ALL THREADS
            # This is a temporary fix until we get the correct event subscriptions
            # Always respond to messages in threads
            logger.info(f"TEMPORARY FIX: Always responding to messages in threads - channel_type: {channel_type}")
            await handle_message(
                text=text,
                user_id=user_id,
                slack_service=slack_service,
                llm_service=llm_service,
                channel=channel,
                thread_ts=thread_ts
            )
            return
            
            # Original code - temporarily disabled:
            # Check thread history to see if bot is part of this thread
            # thread_info = await slack_service.get_thread_info(channel, thread_ts)
            # logger.info(f"Thread info: {thread_info}")
            
            # # Only respond if the bot is already a participant in this thread
            # if thread_info.get("bot_is_participant", False):
            #     logger.info(f"Bot responding to thread - is_participant: true, channel_type: {channel_type}")
            #     await handle_message(
            #         text=text,
            #         user_id=user_id,
            #         slack_service=slack_service,
            #         llm_service=llm_service,
            #         channel=channel,
            #         thread_ts=thread_ts
            #     )
            # else:
            #     logger.info(f"Bot is not a participant in this thread, ignoring - channel_type: {channel_type}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error checking thread history: {error_msg}")
            
            # Permission errors in group or private channels - respond anyway
            logger.info(f"Error occurred, but responding anyway - channel_type: {channel_type}")
            await handle_message(
                text=text,
                user_id=user_id,
                slack_service=slack_service,
                llm_service=llm_service,
                channel=channel,
                thread_ts=thread_ts
            )
        return
            
    logger.info("Message doesn't meet criteria for bot response, ignoring") 
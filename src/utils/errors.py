import logging
import traceback
from typing import Optional
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

async def handle_error(
    client: WebClient, 
    channel: str, 
    thread_ts: Optional[str], 
    error: Exception, 
    error_msg: str = "I'm sorry, something went wrong. Please try again later."
):
    """Centralized error handling for Slack responses"""
    logger.error(f"Error: {error}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    try:
        await client.chat_postMessage(
            channel=channel,
            text=error_msg,
            thread_ts=thread_ts
        )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")

async def delete_message(client: WebClient, channel: str, ts: str) -> bool:
    """Delete a message with error handling"""
    try:
        await client.chat_delete(
            channel=channel,
            ts=ts
        )
        return True
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return False 
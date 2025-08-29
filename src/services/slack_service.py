import logging
import re
import traceback
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config.settings import SlackSettings
from utils.errors import delete_message

logger = logging.getLogger(__name__)


class SlackService:
    """Service for interacting with the Slack API"""

    def __init__(self, settings: SlackSettings, client: WebClient):
        self.settings = settings
        self.client = client
        self.bot_id = settings.bot_id

    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        mrkdwn: bool = True,
    ) -> str | None:
        """Send a message to a Slack channel"""
        try:
            response = await self.client.chat_postMessage(  # type: ignore[misc]
                channel=channel,
                text=text,
                thread_ts=thread_ts,
                blocks=blocks,
                mrkdwn=mrkdwn,
            )
            return response.get("ts")  # type: ignore[no-any-return]
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            return None

    async def send_thinking_indicator(
        self, channel: str, thread_ts: str | None = None
    ) -> str | None:
        """Send a thinking indicator message"""
        try:
            response = await self.client.chat_postMessage(  # type: ignore[misc]
                channel=channel,
                text="⏳ _Thinking..._",
                thread_ts=thread_ts,
                mrkdwn=True,
            )
            ts = response.get("ts")
            logger.info(f"Posted thinking message: {ts}")
            return ts
        except Exception as e:
            logger.error(f"Error posting thinking message: {e}")
            return None

    async def delete_thinking_indicator(self, channel: str, ts: str | None) -> bool:
        """Delete the thinking indicator message"""
        if not ts:
            return False

        return await delete_message(self.client, channel, ts)

    async def get_thread_history(
        self, channel: str, thread_ts: str, limit: int = 20
    ) -> tuple[list[dict[str, str]], bool]:
        """Get message history from a thread"""
        messages = []
        success = False

        try:
            logger.info(f"Retrieving thread history for thread {thread_ts}")
            history_response = await self.client.conversations_replies(  # type: ignore[misc]
                channel=channel, ts=thread_ts, limit=limit
            )

            if history_response and history_response.get("messages"):
                raw_messages = history_response["messages"]
                logger.info(
                    f"Retrieved {len(raw_messages)} messages from thread history"
                )

                # Get bot's user ID to identify bot messages
                if not self.bot_id:
                    bot_info = await self.client.auth_test()  # type: ignore[misc]
                    self.bot_id = bot_info.get("user_id")

                # Process each message in the thread
                for msg in raw_messages:
                    msg_text = msg.get("text", "").strip()
                    msg_user = msg.get("user")

                    # Clean up message text (remove mentions)
                    if "<@" in msg_text:
                        msg_text = re.sub(r"<@[A-Z0-9]+>", "", msg_text).strip()

                    # Skip empty messages
                    if not msg_text:
                        continue

                    # Add to thread messages with appropriate role
                    if msg_user == self.bot_id:
                        messages.append({"role": "assistant", "content": msg_text})
                    else:
                        messages.append({"role": "user", "content": msg_text})

                success = True
                logger.info(
                    f"Processed {len(messages)} meaningful messages from thread"
                )
        except Exception as e:
            logger.error(f"Error retrieving thread history: {e}")

            logger.error(f"Thread history error traceback: {traceback.format_exc()}")

        return messages, success

    async def get_thread_info(self, channel: str, thread_ts: str) -> dict:
        """Get information about a thread, including whether the bot is part of it"""
        thread_info = {
            "exists": False,
            "message_count": 0,
            "bot_is_participant": False,
            "messages": [],
            "participant_ids": set(),
            "error": None,
        }

        try:
            # Get the messages in the thread
            logger.info(
                f"Retrieving thread info for thread {thread_ts} in channel {channel}"
            )
            history_response = await self.client.conversations_replies(  # type: ignore[misc]
                channel=channel,
                ts=thread_ts,
                limit=100,  # Get a good sample of the thread
            )

            if history_response and history_response.get("messages"):
                messages = history_response["messages"]
                thread_info["exists"] = True
                thread_info["message_count"] = len(messages)
                thread_info["messages"] = messages

                # Get both bot's user ID and bot ID if we don't have them yet
                if not hasattr(self, "bot_user_id") or not self.bot_user_id:
                    bot_info = await self.client.auth_test()  # type: ignore[misc]
                    self.bot_user_id = bot_info.get("user_id")  # Bot's user ID (U...)
                    actual_bot_id = bot_info.get("bot_id")  # Bot's bot ID (B...)

                    # Log what we got from auth_test
                    logger.info(
                        f"Auth test results: user_id={self.bot_user_id}, bot_id={actual_bot_id}"
                    )

                    # Keep the existing bot_id if it's already set, but store the user_id separately
                    if actual_bot_id:
                        logger.info(
                            f"Updating bot_id from {self.bot_id} to {actual_bot_id}"
                        )
                        self.bot_id = actual_bot_id

                # Check if the bot is a participant and collect all participant IDs
                for msg in messages:
                    user_id = msg.get("user")
                    bot_id = msg.get("bot_id")

                    if user_id:
                        thread_info["participant_ids"].add(user_id)

                    # Check both possible ways the bot could appear in messages:
                    # 1. As a user (user_id field)
                    # 2. As a bot (bot_id field)
                    is_bot_message = (
                        user_id
                        and (
                            user_id == self.bot_id
                            or user_id == getattr(self, "bot_user_id", None)
                        )
                    ) or (
                        bot_id
                        and (
                            bot_id == self.bot_id
                            or bot_id == getattr(self, "bot_user_id", None)
                        )
                    )

                    if is_bot_message:
                        thread_info["bot_is_participant"] = True

                # Convert participant_ids to a list for serialization
                thread_info["participant_ids"] = list(thread_info["participant_ids"])

                logger.info(
                    f"Thread info: exists={thread_info['exists']}, count={thread_info['message_count']}, bot_participant={thread_info['bot_is_participant']}"
                )
                logger.info(
                    f"Thread participants: {thread_info['participant_ids']}, bot_user_id={getattr(self, 'bot_user_id', None)}, bot_id={self.bot_id}"
                )
        except Exception as e:
            error_msg = str(e)
            thread_info["error"] = error_msg
            logger.error(f"Error getting thread info: {error_msg}")

            # Check if this is a permission error
            if "missing_scope" in error_msg:
                needed_scope = "unknown"
                if "needed" in error_msg:
                    # Try to extract the needed scope from the error message

                    match = re.search(r"needed: '([^']+)'", error_msg)
                    if match:
                        needed_scope = match.group(1)

                logger.error(
                    f"Missing permission scope: {needed_scope}. Add this to your Slack app configuration."
                )
                thread_info["error"] = f"Missing permission scope: {needed_scope}"

        return thread_info

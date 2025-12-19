import logging
import os
import re
import traceback
from io import BytesIO
from typing import Any

from slack_sdk import WebClient
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from config.settings import SlackSettings
from models import ThreadInfo
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
    ) -> dict[str, Any] | None:
        """Send a message to a Slack channel

        Returns:
            Response dict with 'ts' key for the message timestamp, or None on error
        """
        try:
            response = await self.client.chat_postMessage(  # type: ignore[misc]
                channel=channel,
                text=text,
                thread_ts=thread_ts,
                blocks=blocks,
                mrkdwn=mrkdwn,
            )
            return response  # type: ignore[no-any-return]
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            return None

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Update an existing Slack message

        Args:
            channel: Channel ID containing the message
            ts: Timestamp of the message to update
            text: New text content
            blocks: Optional blocks for rich formatting

        Returns:
            Response dict, or None on error
        """
        try:
            response = await self.client.chat_update(  # type: ignore[misc]
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks,
            )
            return response  # type: ignore[no-any-return]
        except SlackApiError as e:
            logger.error(f"Error updating message: {e}")
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
        self, channel: str, thread_ts: str | None, limit: int = 20
    ) -> tuple[list[dict[str, str]], bool]:
        """Get message history from a thread"""
        messages = []
        success = False

        # If no thread_ts, this is a new conversation - return empty history
        if thread_ts is None:
            logger.info(
                "No thread_ts provided - starting new conversation with empty history"
            )
            return messages, True

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

    async def upload_file(
        self,
        channel: str,
        file_content: BytesIO | bytes,
        filename: str,
        title: str | None = None,
        initial_comment: str | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any] | None:
        """Upload a file to a Slack channel or thread.

        Args:
            channel: Channel ID to upload to
            file_content: File content as BytesIO or bytes
            filename: Name of the file
            title: Optional file title
            initial_comment: Optional comment to post with file
            thread_ts: Optional thread timestamp to upload in thread

        Returns:
            Response dict with file info, or None on error
        """
        try:
            logger.info(f"Uploading file '{filename}' to channel {channel}")

            response = await self.client.files_upload_v2(  # type: ignore[misc]
                channel=channel,
                file=file_content,
                filename=filename,
                title=title or filename,
                initial_comment=initial_comment,
                thread_ts=thread_ts,
            )

            if response.get("ok"):
                file_info = response.get("file", {})
                logger.info(
                    f"File uploaded successfully: {file_info.get('name')} ({file_info.get('size')} bytes)"
                )
                return response  # type: ignore[no-any-return]
            else:
                logger.error(f"File upload failed: {response.get('error')}")
                return None

        except SlackApiError as e:
            logger.error(f"Error uploading file: {e.response.get('error')}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            return None

    async def get_thread_info(self, channel: str, thread_ts: str) -> ThreadInfo:
        """Get information about a thread, including whether the bot is part of it"""
        # Initialize with defaults
        exists = False
        message_count = 0
        bot_is_participant = False
        messages = []
        participant_ids: set[str] = set()
        error = None

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
                exists = True
                message_count = len(messages)

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
                        participant_ids.add(user_id)

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
                        bot_is_participant = True

                logger.info(
                    f"Thread info: exists={exists}, count={message_count}, bot_participant={bot_is_participant}"
                )
                logger.info(
                    f"Thread participants: {list(participant_ids)}, bot_user_id={getattr(self, 'bot_user_id', None)}, bot_id={self.bot_id}"
                )
        except Exception as e:
            error_msg = str(e)
            error = error_msg
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
                error = f"Missing permission scope: {needed_scope}"

        return ThreadInfo(
            exists=exists,
            message_count=message_count,
            bot_is_participant=bot_is_participant,
            messages=messages,
            participant_ids=list(participant_ids),
            error=error,
            channel=channel,
            thread_ts=thread_ts,
        )

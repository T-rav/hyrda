"""
Conversation Context Manager

Manages conversation context with sliding window and automatic summarization.
Industry-standard approach: keep recent messages + rolling summary.
"""

import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages conversation context with automatic summarization.

    Uses sliding window approach:
    - Keep last N messages in full detail
    - Summarize older messages into rolling summary
    - Never exceed context window limits
    """

    def __init__(
        self,
        llm_provider,
        max_messages: int = 20,
        keep_recent: int = 4,
        summarize_threshold: float = 0.75,
        model_context_window: int = 128000,
    ):
        """
        Initialize conversation manager.

        Args:
            llm_provider: LLM provider for summarization
            max_messages: Maximum messages to keep in full (default: 20)
            keep_recent: Messages to keep when summarizing (default: 4)
            summarize_threshold: Context usage % to trigger summarization (default: 0.75)
            model_context_window: Model's max context tokens (default: 128k for GPT-4o)
        """
        self.llm_provider = llm_provider
        self.max_messages = max_messages
        self.keep_recent = keep_recent
        self.summarize_threshold = summarize_threshold
        self.model_context_window = model_context_window
        self.max_context_tokens = int(model_context_window * summarize_threshold)

    def should_summarize(self, messages: list[dict[str, str]]) -> bool:
        """
        Check if conversation should be summarized.

        Uses simple heuristic: if message count exceeds max_messages.
        More sophisticated: could count tokens.

        Args:
            messages: Conversation messages

        Returns:
            True if summarization needed
        """
        return len(messages) > self.max_messages

    def estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        """
        Estimate token count for messages.

        Uses rough approximation: 1 token ≈ 0.75 words ≈ 4 chars.

        Args:
            messages: Conversation messages

        Returns:
            Estimated token count
        """
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return int(total_chars / 4)  # 4 chars per token approximation

    async def manage_context(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None,
        existing_summary: str | None = None,
    ) -> tuple[str | None, list[dict[str, str]]]:
        """
        Manage conversation context with summarization.

        Args:
            messages: Full conversation history
            system_message: Base system prompt
            existing_summary: Previous summary (if any)

        Returns:
            Tuple of (updated_system_message, managed_messages)
        """
        # Short conversation: no summarization needed
        if not self.should_summarize(messages):
            logger.info(
                f"Conversation has {len(messages)} messages, no summarization needed"
            )
            return system_message, messages

        # Long conversation: summarize old messages
        logger.info(
            f"Conversation has {len(messages)} messages, triggering summarization"
        )

        # Keep last N recent messages, summarize the rest
        recent_messages = messages[-self.keep_recent :]
        old_messages = messages[: -self.keep_recent]

        # Create summary of old messages
        try:
            summary = await self._summarize_messages(old_messages, existing_summary)

            # Build updated system message with summary
            updated_system = self._build_system_with_summary(system_message, summary)

            logger.info(
                f"✅ Summarized {len(old_messages)} old messages, keeping {len(recent_messages)} recent"
            )

            return updated_system, recent_messages

        except Exception as e:
            logger.error(f"Error during summarization: {e}, using sliding window only")
            # Fallback: just use sliding window without summary
            return system_message, messages[-self.max_messages :]

    async def _summarize_messages(
        self, messages: list[dict[str, str]], existing_summary: str | None = None
    ) -> str:
        """
        Summarize conversation messages.

        If existing summary provided, creates incremental summary.

        Args:
            messages: Messages to summarize
            existing_summary: Previous summary to build upon

        Returns:
            Summary text
        """
        if not messages:
            return existing_summary or ""

        # Format messages for summarization
        conversation_text = self._format_messages_for_summary(messages)

        # Build summarization prompt
        if existing_summary:
            # Incremental summarization
            prompt = f"""You are summarizing a conversation to preserve context while reducing token usage.

**Previous Summary:**
{existing_summary}

**New Messages to Incorporate:**
{conversation_text}

Please create an updated summary that:
1. Preserves key information from the previous summary
2. Incorporates important points from the new messages
3. Maintains chronological flow
4. Focuses on facts, decisions, and context needed for future responses
5. Keeps the summary concise (max 500 words)

Updated Summary:"""
        else:
            # First-time summarization
            prompt = f"""You are summarizing a conversation to preserve context while reducing token usage.

**Conversation to Summarize:**
{conversation_text}

Please create a concise summary that:
1. Captures key information, decisions, and context
2. Maintains chronological flow
3. Focuses on facts needed for future responses
4. Keeps it concise (max 500 words)

Summary:"""

        # Get summary from LLM
        summary_messages = [{"role": "user", "content": prompt}]

        summary = await self.llm_provider.get_response(
            messages=summary_messages,
            system_message="You are a conversation summarization assistant. Create clear, concise summaries that preserve important context.",
            max_tokens=1000,  # Limit summary length
        )

        if isinstance(summary, dict):
            summary = summary.get("content", "")

        return summary or existing_summary or ""

    def _format_messages_for_summary(self, messages: list[dict[str, str]]) -> str:
        """
        Format messages into readable text for summarization.

        Args:
            messages: Messages to format

        Returns:
            Formatted conversation text
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
            elif role == "system":
                # Skip system messages in summary
                continue

        return "\n\n".join(formatted)

    def _build_system_with_summary(self, base_system: str | None, summary: str) -> str:
        """
        Build system message with conversation summary.

        Args:
            base_system: Base system prompt
            summary: Conversation summary

        Returns:
            Combined system message
        """
        base = base_system or ""

        if summary:
            return f"""{base}

---

**Previous Conversation Summary:**

{summary}

---

The summary above provides context from earlier in this conversation. Continue naturally based on both the summary and the recent messages."""

        return base

    def get_managed_history(
        self,
        messages: list[dict[str, str]],
        summary: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Get managed message history (for display/caching).

        Args:
            messages: Recent messages
            summary: Current summary

        Returns:
            Messages to cache
        """
        # We only cache recent messages + summary
        # Summary is stored separately in cache
        return messages[-self.max_messages :]


# Token estimation utilities
def estimate_message_tokens(messages: list[dict[str, str]]) -> int:
    """
    Estimate total tokens for message list.

    Args:
        messages: Messages to estimate

    Returns:
        Estimated token count
    """
    total_chars = sum(len(msg.get("content", "")) for msg in messages)
    return int(total_chars / 4)  # Rough approximation


def should_trigger_summarization(
    messages: list[dict[str, str]], max_messages: int = 20
) -> bool:
    """
    Check if summarization should be triggered.

    Args:
        messages: Conversation messages
        max_messages: Threshold for triggering summarization

    Returns:
        True if summarization needed
    """
    return len(messages) > max_messages

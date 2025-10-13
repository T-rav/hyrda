"""Context manager for MEDDPICC coach workflow.

Handles conversation history accumulation, semantic compression, and context building
for multi-turn MEDDPICC coaching conversations.
"""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from config.settings import Settings

logger = logging.getLogger(__name__)


class MeddpiccContextManager:
    """Manages conversation context for MEDDPICC coaching with semantic compression.

    Features:
    - Full conversation history tracking
    - Automatic semantic compression when context grows large
    - Sliding window: keep recent messages + summary of older ones
    - Context-aware prompt building for analysis and follow-ups
    """

    def __init__(
        self,
        max_messages: int | None = None,
        keep_recent: int | None = None,
        summarize_threshold: float | None = None,
        model_context_window: int | None = None,
    ):
        """Initialize context manager.

        Args:
            max_messages: Max messages before compression (from CONVERSATION_MAX_MESSAGES)
            keep_recent: Messages to keep in full during compression (from CONVERSATION_KEEP_RECENT)
            summarize_threshold: Context usage % to trigger compression (from CONVERSATION_SUMMARIZE_THRESHOLD, e.g., 0.80)
            model_context_window: Model's max context tokens (from CONVERSATION_MODEL_CONTEXT_WINDOW)
        """
        # Load from settings if not provided
        if (
            max_messages is None
            or keep_recent is None
            or summarize_threshold is None
            or model_context_window is None
        ):
            from config.settings import Settings

            settings = Settings()
            max_messages = max_messages or settings.conversation.max_messages
            keep_recent = keep_recent or settings.conversation.keep_recent
            summarize_threshold = (
                summarize_threshold or settings.conversation.summarize_threshold
            )
            model_context_window = (
                model_context_window or settings.conversation.model_context_window
            )

        self.max_messages = max_messages
        self.keep_recent = keep_recent
        self.summarize_threshold = summarize_threshold
        self.model_context_window = model_context_window
        # Calculate token threshold from percentage
        self.summarize_threshold_tokens = int(
            model_context_window * summarize_threshold
        )

        logger.info(
            f"📊 Context manager initialized: max_messages={self.max_messages}, "
            f"keep_recent={self.keep_recent}, threshold={self.summarize_threshold:.0%} "
            f"({self.summarize_threshold_tokens} tokens)"
        )

    def add_message(
        self,
        conversation_history: list[dict[str, str]],
        role: str,
        content: str,
    ) -> list[dict[str, str]]:
        """Add a new message to conversation history.

        Args:
            conversation_history: Existing history (may be empty)
            role: Message role ("user" or "assistant")
            content: Message content

        Returns:
            Updated conversation history
        """
        if not conversation_history:
            conversation_history = []

        conversation_history.append({"role": role, "content": content})
        logger.info(
            f"📝 Added {role} message ({len(content)} chars) - total: {len(conversation_history)} messages"
        )
        return conversation_history

    def should_compress(
        self,
        conversation_history: list[dict[str, str]],
        conversation_summary: str | None = None,
    ) -> bool:
        """Check if conversation should be compressed.

        Args:
            conversation_history: Full conversation history
            conversation_summary: Existing summary (if any)

        Returns:
            True if compression needed
        """
        # Check message count
        if len(conversation_history) > self.max_messages:
            logger.info(
                f"🗜️ Compression needed: {len(conversation_history)} > {self.max_messages} messages"
            )
            return True

        # Estimate tokens (rough: ~4 chars per token)
        total_chars = sum(msg.get("content", "") for msg in conversation_history)
        estimated_tokens = len(total_chars) // 4

        if conversation_summary:
            estimated_tokens += len(conversation_summary) // 4

        if estimated_tokens > self.summarize_threshold_tokens:
            logger.info(
                f"🗜️ Compression needed: ~{estimated_tokens} tokens > {self.summarize_threshold_tokens}"
            )
            return True

        return False

    async def compress_history(
        self,
        conversation_history: list[dict[str, str]],
        existing_summary: str | None = None,
    ) -> tuple[list[dict[str, str]], str]:
        """Compress conversation history using semantic summarization.

        Keeps recent messages in full, summarizes older ones.

        Args:
            conversation_history: Full conversation history
            existing_summary: Previous summary to build upon

        Returns:
            Tuple of (compressed_history, new_summary)
            - compressed_history: Recent messages only
            - new_summary: Summary of older messages + previous summary
        """
        if len(conversation_history) <= self.keep_recent:
            return conversation_history, existing_summary or ""

        # Split into old (to summarize) and recent (to keep)
        old_messages = conversation_history[: -self.keep_recent]
        recent_messages = conversation_history[-self.keep_recent :]

        logger.info(
            f"🗜️ Compressing {len(old_messages)} messages, keeping {len(recent_messages)} recent"
        )

        # Build summarization prompt
        messages_text = "\n\n".join(
            [
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in old_messages
            ]
        )

        # Build previous summary section (can't use \n in f-string conditional)
        previous_summary_section = ""
        if existing_summary:
            previous_summary_section = f"Previous Summary:\n{existing_summary}\n\n"

        summarization_prompt = f"""You are summarizing a MEDDPICC sales coaching conversation.

{previous_summary_section}Messages to Summarize:
{messages_text}

Create a concise but comprehensive summary that:
1. Captures all key sales information (company, contacts, pain points, metrics, process, etc.)
2. Preserves important details and context
3. Notes any Q&A interactions or clarifications
4. Maintains chronological flow
5. Keeps it under 500 words

Summary:"""

        try:
            settings = Settings()
            llm = ChatOpenAI(
                model="gpt-4o-mini",  # Fast model for summarization
                temperature=0.3,  # Low temp for factual summary
                api_key=settings.llm.api_key,
            )

            response = await llm.ainvoke(summarization_prompt)
            new_summary = (
                response.content if hasattr(response, "content") else str(response)
            )

            logger.info(
                f"✅ Compressed {len(old_messages)} messages → {len(new_summary)} char summary"
            )
            return recent_messages, new_summary

        except Exception as e:
            logger.error(f"❌ Compression failed: {e}")
            # Fallback: keep more recent messages, simple summary
            fallback_recent = conversation_history[-self.keep_recent * 2 :]
            fallback_summary = f"{existing_summary or ''}\n\n[Older messages: {len(old_messages)} interactions about sales analysis]"
            return fallback_recent, fallback_summary

    def build_context_prompt(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
        conversation_summary: str | None = None,
        mode: str = "analysis",
    ) -> str:
        """Build contextual prompt for MEDDPICC analysis or follow-up.

        Args:
            query: Current user query
            conversation_history: Recent conversation messages
            conversation_summary: Summary of older messages
            mode: "analysis", "followup", or "qa"

        Returns:
            Enhanced prompt with full context
        """
        context_parts = []

        # Add conversation summary if available
        if conversation_summary:
            context_parts.append(
                f"<Previous Conversation Summary>\n{conversation_summary}\n</Previous Conversation Summary>"
            )

        # Add recent conversation history
        if conversation_history and len(conversation_history) > 1:
            # Exclude the current query (it's the last message)
            recent_history = conversation_history[:-1]
            if recent_history:
                history_text = "\n\n".join(
                    [
                        f"{'User' if msg['role'] == 'user' else 'Assistant'}: {str(msg.get('content', ''))[:300]}{'...' if len(str(msg.get('content', ''))) > 300 else ''}"
                        for msg in recent_history[-5:]  # Last 5 messages max
                    ]
                )
                context_parts.append(
                    f"<Recent Conversation>\n{history_text}\n</Recent Conversation>"
                )

        # Build full prompt based on mode
        if mode == "analysis":
            if context_parts:
                return f"{chr(10).join(context_parts)}\n\n<Current Sales Information>\n{query}\n</Current Sales Information>"
            return query

        elif mode == "followup":
            if context_parts:
                return f"{chr(10).join(context_parts)}\n\n<Current Question>\n{query}\n</Current Question>"
            return query

        else:  # qa mode
            return query  # Q&A doesn't need historical context

    async def manage_context(
        self,
        query: str,
        conversation_history: list[dict[str, str]] | None,
        conversation_summary: str | None,
        role: str = "user",
    ) -> dict[str, Any]:
        """Manage context: add message, compress if needed, build prompt.

        Args:
            query: Current user query
            conversation_history: Existing history (or None)
            conversation_summary: Existing summary (or None)
            role: Role of the query message

        Returns:
            Dict with:
            - conversation_history: Updated history
            - conversation_summary: Updated summary
            - enhanced_query: Query with full context
        """
        # Add current message
        history = self.add_message(conversation_history or [], role, query)

        # Check if compression needed
        if self.should_compress(history, conversation_summary):
            history, conversation_summary = await self.compress_history(
                history, conversation_summary
            )

        # Build contextual prompt
        enhanced_query = self.build_context_prompt(
            query, history, conversation_summary, mode="analysis"
        )

        return {
            "conversation_history": history,
            "conversation_summary": conversation_summary or "",
            "enhanced_query": enhanced_query,
        }

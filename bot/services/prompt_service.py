"""
Prompt Management Service

Centralized service for managing system prompts with support for:
- Langfuse prompt templates (primary)
- Local fallback prompts (secondary)
- Caching for performance
- Version management
"""

import logging
from typing import Any

from config.settings import Settings
from services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)

# Default system message as fallback when Langfuse is unavailable
DEFAULT_SYSTEM_MESSAGE = """I'm Insight Mesh, your intelligent AI assistant powered by advanced RAG (Retrieval-Augmented Generation) technology. I'm designed to help you efficiently explore, understand, and work with your organization's knowledge base and data assets.

I provide precise, well-sourced answers from your organization's documented knowledge - not generic information from the internet. Think of me as your dedicated research assistant who has comprehensive access to your company's information architecture and can quickly surface relevant insights to support your decision-making.

## Core Capabilities:
- **Advanced Knowledge Retrieval**: I search through your ingested documents using hybrid retrieval technology that combines semantic similarity matching with keyword-based search to provide highly accurate, context-aware responses
- **Comprehensive Source Attribution**: I always cite the specific documents, sections, and data sources that inform my responses, providing complete transparency about information provenance so you can verify and dive deeper as needed
- **Thread-Aware Conversations**: I maintain full conversation context across Slack threads, remembering previous exchanges and building upon earlier discussions to provide coherent, progressive assistance
- **Automated Agent Processes**: I can initiate and coordinate background data processing jobs including document indexing, data imports, knowledge base updates, and other automated organizational tasks
- **Multi-Format Document Processing**: I can analyze and extract insights from PDFs, Word documents, spreadsheets, presentations, and other business document formats that you upload or reference
- **Cross-Reference Analysis**: I can identify connections and relationships between different documents and data sources in your knowledge base to provide comprehensive, multi-faceted answers

## Communication Standards:
- I maintain a professional, efficient communication style appropriate for executive-level interactions while remaining accessible to users at all organizational levels
- I use clear, business-appropriate language that respects your time constraints and information needs
- I integrate retrieved information seamlessly into responses without awkward transitions or obvious templating
- I maintain intellectual honesty and transparency - if I'm uncertain about information or if my confidence is low, I communicate this clearly rather than speculate or provide potentially misleading guidance
- I adapt my response depth and technical detail level based on the complexity of your question and apparent expertise level
- I proactively surface related information that might be valuable for your broader context or decision-making needs

## Information Handling Protocols:
- **Primary Source Priority**: When relevant documents are found in your knowledge base, I use that organizational information as my primary source and cite it comprehensively
- **Transparency in Source Limitations**: If no relevant context is retrieved from your knowledge base, I clearly indicate that I'm responding based on general knowledge rather than your specific organizational information
- **Accuracy Over Completeness**: I always prioritize factual accuracy over comprehensive coverage - it's better to acknowledge limitations in available information than to speculate or provide potentially inaccurate guidance
- **Source Verification Support**: I maintain conversation flow while being completely transparent about my information sources, enabling you to verify claims and explore source materials independently
- **Context Preservation**: I consider the broader business context and implications when providing information, not just narrow technical answers
- **Sensitive Information Awareness**: I'm designed to recognize when information might be confidential or sensitive and handle such content appropriately

## Slack Integration Behaviors:
- **Seamless Thread Participation**: I automatically participate in threads once mentioned - you don't need to @mention me again within the same conversation thread
- **Real-Time Feedback**: I show typing indicators while processing your requests so you know I'm actively working on your query
- **Universal Accessibility**: I work consistently across all Slack contexts including direct messages, public channels, private channels, and group conversations
- **Conversation History Integration**: I can reference and build upon previous messages in ongoing threads to maintain conversational continuity
- **Multi-User Thread Handling**: In group conversations, I can distinguish between different participants and maintain context for multiple concurrent discussion threads

## Advanced Features:
- **Hybrid Search Intelligence**: I automatically determine the optimal search strategy for your query, combining dense semantic search with sparse keyword matching for comprehensive coverage
- **Entity Recognition and Boosting**: I identify key entities (people, companies, products, concepts) in your questions and boost relevance for documents containing those entities
- **Document Diversification**: I intelligently balance results from multiple sources to provide comprehensive coverage while avoiding over-representation from any single document
- **Contextual Understanding**: I can process documents you upload in real-time during conversations, immediately incorporating that information into our discussion
- **Business Process Integration**: I can execute and coordinate various automated business processes, from data imports to knowledge base maintenance, based on your natural language requests

## Response Quality Standards:
- **Executive-Ready Output**: My responses are structured and comprehensive enough to support high-level decision-making while being concise and actionable
- **Source Transparency**: I provide clear attribution for all information, enabling quick verification and deeper exploration of relevant materials
- **Conversational Flow**: I maintain natural dialogue flow while ensuring technical accuracy and business relevance
- **Adaptive Complexity**: I match my response complexity and technical depth to the sophistication of your question and your apparent expertise level
- **Proactive Value Addition**: I identify and surface related insights that might be valuable for your broader objectives, even if not explicitly requested

My core strength lies in efficiently connecting you with your organization's documented knowledge while providing intelligent, contextual assistance tailored to your specific business needs and strategic objectives. I'm designed to enhance your productivity by serving as an always-available, comprehensive gateway to your organizational intelligence."""


class PromptService:
    """
    Service for managing system and user prompts with Langfuse integration
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.langfuse_settings = settings.langfuse
        self._cached_system_prompt: str | None = None
        self._prompt_cache: dict[str, str] = {}

    def get_system_prompt(self, force_refresh: bool = False) -> str:
        """
        Get the system prompt, preferring Langfuse template over local default

        Args:
            force_refresh: Force refresh from Langfuse even if cached

        Returns:
            The system prompt string
        """
        # Return cached version unless force refresh
        if self._cached_system_prompt and not force_refresh:
            return self._cached_system_prompt

        # Try to get from Langfuse if enabled
        if self.langfuse_settings.use_prompt_templates:
            langfuse_prompt = self._get_langfuse_system_prompt()
            if langfuse_prompt:
                self._cached_system_prompt = langfuse_prompt
                logger.info(
                    f"Using Langfuse system prompt template: {self.langfuse_settings.system_prompt_template}"
                )
                return langfuse_prompt

        # Fallback to local default
        self._cached_system_prompt = DEFAULT_SYSTEM_MESSAGE
        logger.info("Using local default system prompt (Langfuse unavailable/disabled)")
        return DEFAULT_SYSTEM_MESSAGE

    def _get_langfuse_system_prompt(self) -> str | None:
        """
        Get system prompt from Langfuse template

        Returns:
            The prompt string from Langfuse or None if failed
        """
        try:
            langfuse_service = get_langfuse_service()
            if not langfuse_service:
                logger.warning("Langfuse service not available")
                return None

            prompt = langfuse_service.get_prompt_template(
                template_name=self.langfuse_settings.system_prompt_template,
                version=self.langfuse_settings.prompt_template_version,
            )

            if prompt:
                logger.debug("Successfully fetched system prompt from Langfuse")
                return prompt
            else:
                logger.warning(
                    f"Langfuse prompt template '{self.langfuse_settings.system_prompt_template}' not found"
                )
                return None

        except Exception as e:
            logger.error(f"Error fetching system prompt from Langfuse: {e}")
            return None

    def get_custom_prompt(
        self,
        template_name: str,
        version: str | None = None,
        fallback: str | None = None,
    ) -> str | None:
        """
        Get a custom prompt template from Langfuse

        Args:
            template_name: Name of the prompt template
            version: Specific version (uses latest if None)
            fallback: Fallback text if template not found

        Returns:
            The prompt string or fallback
        """
        cache_key = f"{template_name}:{version or 'latest'}"

        # Check cache first
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        # Try Langfuse
        if self.langfuse_settings.use_prompt_templates:
            try:
                langfuse_service = get_langfuse_service()
                if langfuse_service:
                    prompt = langfuse_service.get_prompt_template(
                        template_name, version
                    )
                    if prompt:
                        self._prompt_cache[cache_key] = prompt
                        logger.debug(f"Fetched custom prompt template: {template_name}")
                        return prompt
            except Exception as e:
                logger.error(f"Error fetching custom prompt '{template_name}': {e}")

        # Return fallback or None
        if fallback:
            self._prompt_cache[cache_key] = fallback
            logger.debug(f"Using fallback for prompt template: {template_name}")
            return fallback

        logger.warning(f"Custom prompt template '{template_name}' not found")
        return None

    def clear_cache(self):
        """Clear the prompt cache to force refresh from Langfuse"""
        self._cached_system_prompt = None
        self._prompt_cache.clear()
        logger.debug("Prompt cache cleared")

    def get_prompt_info(self) -> dict[str, Any]:
        """
        Get information about current prompt configuration

        Returns:
            Dictionary with prompt configuration details
        """
        return {
            "langfuse_enabled": self.langfuse_settings.enabled,
            "use_prompt_templates": self.langfuse_settings.use_prompt_templates,
            "system_prompt_template": self.langfuse_settings.system_prompt_template,
            "template_version": self.langfuse_settings.prompt_template_version,
            "cached_system_prompt": self._cached_system_prompt is not None,
            "cache_size": len(self._prompt_cache),
        }


# Global instance - will be initialized by the main application
_prompt_service: PromptService | None = None


def get_prompt_service() -> PromptService | None:
    """Get the global prompt service instance"""
    return _prompt_service


def initialize_prompt_service(settings: Settings) -> PromptService:
    """Initialize the global prompt service"""
    global _prompt_service  # noqa: PLW0603
    _prompt_service = PromptService(settings)
    return _prompt_service

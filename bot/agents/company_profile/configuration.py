"""Configuration for company profile deep research workflow.

Centralized, type-safe configuration for profile research agent.
"""

import os
from enum import Enum

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from config.settings import Settings


class SearchAPI(str, Enum):
    """Available search API options."""

    WEBCAT = "webcat"  # Our integrated WebCat MCP server
    TAVILY = "tavily"  # Tavily search (if available)
    NONE = "none"  # No search API


class PDFStyle(str, Enum):
    """Available PDF styling options."""

    MINIMAL = "minimal"  # Clean, minimal styling
    PROFESSIONAL = "professional"  # Professional business styling (default)
    DETAILED = "detailed"  # Detailed with enhanced metadata


class ProfileConfiguration(BaseModel):
    """Configuration for profile research agent.

    All settings can be overridden via environment variables or runtime config.
    """

    # General settings
    max_structured_output_retries: int = 3
    allow_clarification: bool = False  # Disabled - queries are typically clear enough
    max_concurrent_research_units: int = 3  # Conservative for company profiles

    # Search configuration
    search_api: SearchAPI = SearchAPI.WEBCAT  # Use our WebCat integration
    max_researcher_iterations: int = (
        8  # Supervisor reflection cycles (increased for deeper investigation)
    )
    max_react_tool_calls: int = (
        15  # Max tool calls per researcher (increased for multi-angle investigation)
    )

    # Model configuration (reuse existing LLM settings)
    # Format: "provider:model" but we'll use configured LLM
    research_model: str = "openai:gpt-4o-mini"  # Main research model
    compression_model: str = "openai:gpt-4o-mini"  # Compression model
    final_report_model: str = "openai:gpt-4o"  # Final report generation

    # Token limits (uses centralized Settings.conversation.model_context_window)
    # Default to reasonable portions of the 128K context window
    # These can be overridden via environment variables
    research_model_max_tokens: int = (
        16000  # For researcher tool calling with large payloads
    )
    compression_model_max_tokens: int = (
        64000  # Half of 128K - handles massive deep_research payloads!
    )
    final_report_model_max_tokens: int = (
        32000  # Half of compression (64K) - rich, well-cited deep research reports
    )

    # Profile-specific settings
    min_profile_sections: int = 3  # Minimum sections in final report
    include_sources: bool = True  # Include source citations
    profile_depth: str = "detailed"  # "brief", "detailed", "comprehensive"

    # PDF report settings
    pdf_style: PDFStyle = PDFStyle.PROFESSIONAL  # PDF styling preset

    @classmethod
    def from_runnable_config(
        cls, config: RunnableConfig | None = None
    ) -> "ProfileConfiguration":
        """Load configuration from environment variables or RunnableConfig.

        Args:
            config: Optional RunnableConfig from LangGraph

        Returns:
            ProfileConfiguration instance with merged settings
        """
        # Start with defaults
        settings = {}

        # Try to use centralized Settings for model context window
        # This respects CONVERSATION_MODEL_CONTEXT_WINDOW from .env
        try:
            app_settings = Settings()
            context_window = app_settings.conversation.model_context_window

            # If no specific token limits set, use reasonable portions of context window
            if not os.getenv("RESEARCH_MODEL_MAX_TOKENS"):
                settings["research_model_max_tokens"] = min(16000, context_window // 8)
            if not os.getenv("COMPRESSION_MODEL_MAX_TOKENS"):
                settings["compression_model_max_tokens"] = min(
                    64000,
                    context_window
                    // 2,  # Half context window - massive payload support
                )
            if not os.getenv("FINAL_REPORT_MODEL_MAX_TOKENS"):
                settings["final_report_model_max_tokens"] = min(
                    32000,
                    context_window // 4,  # 1/4 context, half of compression limit
                )
        except Exception:  # nosec B110
            # Fallback to defaults if Settings import fails (intentional)
            pass

        # Override with environment variables if present
        for field_name in cls.model_fields:
            env_var = field_name.upper()
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Handle enum types
                if field_name == "search_api":
                    settings[field_name] = SearchAPI(env_value.lower())
                elif field_name == "pdf_style":
                    settings[field_name] = PDFStyle(env_value.lower())
                # Handle boolean types
                elif isinstance(cls.model_fields[field_name].default, bool):
                    settings[field_name] = env_value.lower() in ("true", "1", "yes")
                # Handle numeric types
                elif isinstance(cls.model_fields[field_name].default, int):
                    settings[field_name] = int(env_value)
                else:
                    settings[field_name] = env_value

        # Override with runtime config if present
        if config and "configurable" in config:
            configurable = config["configurable"]
            for key, value in configurable.items():
                if key in cls.model_fields:
                    settings[key] = value

        return cls(**settings)

    @classmethod
    def from_env(cls) -> "ProfileConfiguration":
        """Load configuration from environment variables only.

        Returns:
            ProfileConfiguration instance
        """
        return cls.from_runnable_config(None)

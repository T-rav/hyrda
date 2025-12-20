"""Configuration for company profile deep research workflow.

Centralized, type-safe configuration for profile research agent.
"""

import os
from enum import Enum

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel


class SearchAPI(str, Enum):
    """Available search API options."""

    TAVILY = "tavily"  # Tavily search (direct integration)
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
    max_concurrent_research_units: int = 3  # Balanced parallelization (reduced from 6)

    # Search configuration
    search_api: SearchAPI = SearchAPI.TAVILY  # Use direct Tavily integration
    max_researcher_iterations: int = 12  # Deep research for comprehensive 20+ page reports
    max_react_tool_calls: int = (
        10  # More tool calls per researcher for thorough research
    )

    # Model configuration (reuse existing LLM settings)
    # Format: "provider:model" but we'll use configured LLM
    research_model: str = "openai:gpt-4o-mini"  # Main research model
    compression_model: str = "openai:gpt-4o-mini"  # Compression model
    final_report_model: str = "openai:gpt-4o"  # Final report generation

    # Token limits
    # Note: Gemini 2.5 Pro has 1M input + 64K output tokens
    # OpenAI GPT-4o has 128K input + 16K output tokens
    research_model_max_tokens: int = 16000  # For researcher tool calling
    compression_model_max_tokens: int = 16000  # For compression synthesis
    final_report_model_max_tokens: int = (
        60000  # Gemini 2.5 Pro: 64k max output (using 60k for safety)
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

        # Override with environment variables if present (for other settings)
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

"""Configuration for Lead Qualifier agent."""

import os

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel


class QualifierConfiguration(BaseModel):
    """Configuration for the Lead Qualifier agent.

    All settings can be overridden via environment variables or runtime config.
    """

    # Model configuration
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4000

    # Scoring weights
    solution_fit_weight: int = 40
    strategic_fit_weight: int = 25
    historical_similarity_weight: int = 25

    # Tier thresholds
    high_tier_threshold: int = 75
    medium_tier_threshold: int = 50

    # Service categories
    service_categories: list[str] = [
        "Platform Modernization",
        "Custom Product Development",
        "Data Platform Engineering",
        "AI Enablement",
        "Technical Advisory",
        "Cloud Migration",
        "Engineering Excellence & Delivery Teams",
    ]

    # Search configuration
    vector_search_limit: int = 10
    similarity_threshold: float = 0.7

    @classmethod
    def from_runnable_config(
        cls, config: RunnableConfig | None = None
    ) -> "QualifierConfiguration":
        """Load configuration from environment variables or RunnableConfig.

        Args:
            config: Optional RunnableConfig from LangGraph

        Returns:
            QualifierConfiguration instance with merged settings
        """
        # Start with defaults
        settings = {}

        # Override with environment variables if present
        for field_name in cls.model_fields:
            env_var = field_name.upper()
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Handle numeric types
                if isinstance(cls.model_fields[field_name].default, (int, float)):
                    settings[field_name] = type(cls.model_fields[field_name].default)(
                        env_value
                    )
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
    def from_env(cls) -> "QualifierConfiguration":
        """Load configuration from environment variables only.

        Returns:
            QualifierConfiguration instance
        """
        return cls.from_runnable_config(None)

"""Configuration for MEDDPICC coach workflow.

Centralized, type-safe configuration for MEDDPICC coach agent.
"""

import os

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel


class MeddpiccConfiguration(BaseModel):
    """Configuration for MEDDPICC coach agent.

    All settings can be overridden via environment variables or runtime config.
    """

    # Model configuration
    analysis_model: str = "openai:gpt-4o"  # Main analysis model
    coaching_model: str = "openai:gpt-4o-mini"  # Coaching insights model

    # Token limits
    analysis_max_tokens: int = 4000
    coaching_max_tokens: int = 2000

    # Temperature settings
    analysis_temperature: float = 0.3  # Lower for structured analysis
    coaching_temperature: float = 0.7  # Higher for creative coaching

    @classmethod
    def from_runnable_config(
        cls, config: RunnableConfig | None = None
    ) -> "MeddpiccConfiguration":
        """Load configuration from environment variables or RunnableConfig.

        Args:
            config: Optional RunnableConfig from LangGraph

        Returns:
            MeddpiccConfiguration instance with merged settings
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
    def from_env(cls) -> "MeddpiccConfiguration":
        """Load configuration from environment variables only.

        Returns:
            MeddpiccConfiguration instance
        """
        return cls.from_runnable_config(None)

"""Configuration for Lead Qualifier agent."""

import os

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field


class QualifierConfiguration(BaseModel):
    """Configuration for the Lead Qualifier agent."""

    model_config = ConfigDict(extra="ignore")  # Pydantic v2 syntax
    """Configuration for the Lead Qualifier agent.

    Attributes:
        model: LLM model to use (default: gpt-4o)
        temperature: LLM temperature (default: 0.0 for consistent scoring)
        max_tokens: Maximum tokens for LLM responses
        solution_fit_weight: Weight for solution fit score (max 40)
        strategic_fit_weight: Weight for strategic fit score (max 25)
        historical_similarity_weight: Weight for historical similarity (max 25)
        high_tier_threshold: Minimum score for High tier (default: 75)
        medium_tier_threshold: Minimum score for Medium tier (default: 50)
    """

    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4000

    # Scoring weights (max values)
    solution_fit_weight: int = 40
    strategic_fit_weight: int = 25
    historical_similarity_weight: int = 25

    # Tier thresholds
    high_tier_threshold: int = 75
    medium_tier_threshold: int = 50

    # Service categories (8th Light offerings)
    service_categories: list[str] = Field(
        default_factory=lambda: [
            "Platform Modernization",
            "Custom Product Development",
            "Data Platform Engineering",
            "AI Enablement",
            "Technical Advisory",
            "Cloud Migration",
            "Engineering Excellence & Delivery Teams",
        ]
    )

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
        # Start with defaults - use model_validate to leverage ConfigDict(extra="ignore")
        kwargs = {}

        # Override from environment
        if model := os.getenv("LLM_MODEL"):
            kwargs["model"] = model

        # Override from RunnableConfig if provided
        if config and "configurable" in config:
            kwargs.update(config["configurable"])

        # Use model_validate which respects ConfigDict(extra="ignore")
        return cls.model_validate(kwargs)

"""Shared configuration settings across InsightMesh services."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class LangfuseSettings(BaseSettings):
    """Langfuse observability settings.

    Shared across bot and agent-service for consistent LLM tracing configuration.
    """

    enabled: bool = Field(default=True, description="Enable Langfuse tracing")
    public_key: str = Field(default="", description="Langfuse public key")
    secret_key: SecretStr = Field(
        default=SecretStr(""), description="Langfuse secret key"
    )
    host: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )
    debug: bool = Field(default=False, description="Enable Langfuse debug logging")

    # Prompt template settings
    use_prompt_templates: bool = Field(
        default=True,
        description="Use Langfuse prompt templates instead of hardcoded prompts",
    )
    system_prompt_template: str = Field(
        default="System/Default", description="Langfuse template name for system prompt"
    )
    prompt_template_version: str | None = Field(
        default=None,
        description="Specific prompt template version (uses latest if None)",
    )

    model_config = {"env_prefix": "LANGFUSE_"}

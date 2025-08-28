from pydantic import HttpUrl, SecretStr, Field, ConfigDict
from pydantic_settings import BaseSettings
from typing import Optional

class SlackSettings(BaseSettings):
    """Slack API settings"""
    bot_token: str = Field(description="Slack bot token (xoxb-...)")
    app_token: str = Field(description="Slack app token (xapp-...)")
    bot_id: str = ""
    
    model_config = ConfigDict(env_prefix="SLACK_")

class LLMSettings(BaseSettings):
    """LLM API settings"""
    api_url: str = Field(description="LLM API URL")
    api_key: SecretStr = Field(description="LLM API key")
    model: str = Field(default="gpt-4o-mini", description="LLM model name")
    
    model_config = ConfigDict(env_prefix="LLM_")

class AgentSettings(BaseSettings):
    """Agent process settings"""
    enabled: bool = True
    
    model_config = ConfigDict(env_prefix="AGENT_")

class Settings(BaseSettings):
    """Main application settings"""
    slack: SlackSettings = Field(default_factory=SlackSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    debug: bool = False
    log_level: str = "INFO"
    
    model_config = ConfigDict(env_file=".env", extra="ignore") 
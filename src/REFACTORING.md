# Slack Bot Refactoring Plan

## Current Issues

1. **Monolithic Structure**: All functionality is in a single `app.py` file
2. **Large Functions**: Some functions like `handle_message()` are over 170 lines long
3. **Error Handling**: Inconsistent error handling with duplicated try/except blocks
4. **Configuration**: Hard-coded values and limited configuration options
5. **Testing**: No unit tests or testing infrastructure

## Proposed File Structure

```
slack-bot/
├── config/
│   ├── __init__.py
│   └── settings.py           # Pydantic settings models
├── handlers/
│   ├── __init__.py
│   ├── agent_processes.py    # Agent process functionality
│   ├── event_handlers.py     # Slack event handlers
│   └── message_handlers.py   # Message handling logic
├── services/
│   ├── __init__.py
│   ├── llm_service.py        # LLM interaction
│   ├── slack_service.py      # Slack API interaction
│   └── formatting.py         # Response formatting utilities
├── utils/
│   ├── __init__.py
│   └── logging.py            # Enhanced logging setup
├── tests/
│   ├── __init__.py
│   ├── test_handlers.py
│   └── test_services.py
├── app.py                    # Main entry point (slim)
├── Dockerfile
└── requirements.txt
```

## Specific Refactoring Tasks

### 1. Configuration System

Create a configuration system using Pydantic:

```python
# config/settings.py
from pydantic import BaseSettings, HttpUrl, SecretStr

class SlackSettings(BaseSettings):
    bot_token: SecretStr
    app_token: SecretStr
    bot_id: str = ""
    
    class Config:
        env_prefix = "SLACK_"

class LLMSettings(BaseSettings):
    api_url: HttpUrl
    api_key: SecretStr
    model: str = "gpt-4o-mini"
    
    class Config:
        env_prefix = "LLM_"

class Settings(BaseSettings):
    slack: SlackSettings = SlackSettings()
    llm: LLMSettings = LLMSettings()
    debug: bool = False
    
    class Config:
        env_file = ".env"
```

### 2. Break Down Large Functions

Split `handle_message()` into smaller functions:

1. `fetch_thread_history()`
2. `prepare_llm_messages()`
3. `send_thinking_indicator()`
4. `clear_thinking_indicator()`
5. `process_message()`

### 3. Improve Error Handling

Create consistent error handling utilities:

```python
# utils/errors.py
async def handle_error(client, channel, thread_ts, error, error_msg="I'm sorry, something went wrong"):
    """Centralized error handling for Slack responses"""
    logger.error(f"Error: {error}")
    try:
        await client.chat_postMessage(
            channel=channel,
            text=error_msg,
            thread_ts=thread_ts
        )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")
```

### 4. LLM Service

Extract LLM interaction to a separate service:

```python
# services/llm_service.py
class LLMService:
    def __init__(self, settings: LLMSettings):
        self.api_url = str(settings.api_url)
        self.api_key = settings.api_key.get_secret_value()
        self.model = settings.model
        self.session = None
        
    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def get_response(self, messages, user_id=None):
        """Get response from LLM via API"""
        # Implementation here
        
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
```

### 5. Message Formatting

Extract message formatting to a separate module:

```python
# services/formatting.py
class MessageFormatter:
    @staticmethod
    async def format_slack_message(response):
        """Format message for Slack, including handling Markdown links"""
        # Implementation here
```

### 6. Testing Infrastructure

Add unit tests for critical components:

- Mock Slack API responses
- Test message handling
- Test LLM service with mocked responses

## Implementation Strategy

1. First create the new directory structure and configuration system
2. Extract services one by one while maintaining functionality
3. Refactor the main handlers to use the new services
4. Add tests for each component
5. Update the main app.py to use the new modular structure

## Expected Benefits

1. **Maintainability**: Smaller, focused files are easier to understand and maintain
2. **Testability**: Isolated components allow for better unit testing
3. **Flexibility**: Configuration system makes it easier to adapt to different environments
4. **Reliability**: Consistent error handling improves user experience
5. **Scalability**: Modular structure makes it easier to add new features 
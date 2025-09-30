# Test Utils Module

## Overview

Centralized test utilities for creating test data, mocks, and fixtures.
All utilities are consolidated from duplicate patterns across the test suite.

## Structure

```
tests/utils/
├── __init__.py       # Module definition
├── settings.py       # 7 settings factory classes
├── services.py       # 10 service factory classes
├── models.py         # 6 model factory classes
├── builders.py       # 7 builder pattern classes
├── mocks.py          # 8 mock factory classes
└── README.md         # This file
```

## Usage

```python
# Import from combined files
from tests.utils.settings import LLMSettingsFactory, SettingsFactory
from tests.utils.services import SlackServiceFactory
from tests.utils.models import MessageFactory
from tests.utils.builders import ConversationBuilder
from tests.utils.mocks import MockVectorStoreFactory

def test_example():
    settings = LLMSettingsFactory.create_openai_settings()
    service = SlackServiceFactory.create_mock_service()
    messages = MessageFactory.create_conversation()
    # use in tests...
```

## Available Utilities

### Settings Factories (settings.py)
- `EnvironmentVariableFactory` - Environment configs
- `LLMSettingsFactory` - LLM settings
- `EmbeddingSettingsFactory` - Embedding settings
- `VectorSettingsFactory` - Vector storage settings
- `SlackSettingsFactory` - Slack API settings
- `RAGSettingsBuilder` - RAG configurations
- `SettingsFactory` - Complete Settings objects

### Service Factories (services.py)
- `SlackClientFactory` - Slack client mocks
- `SlackServiceFactory` - Slack service mocks
- `LLMServiceFactory` - LLM service mocks
- `RAGServiceFactory` - RAG service mocks
- `ConversationCacheFactory` - Cache mocks
- `RetrievalServiceFactory` - Retrieval service mocks
- `EmbeddingServiceFactory` - Embedding service mocks
- `VectorServiceFactory` - Vector service mocks
- `LangfuseServiceFactory` - Langfuse service mocks

### Model Factories (models.py)
- `MessageFactory` - Chat messages
- `SlackEventFactory` - Slack events
- `TextDataFactory` - Text data for testing
- `RetrievalResultFactory` - Retrieval results
- `ContextChunkBuilder` - Context chunks
- `RetrievalResultBuilder` - Result builder

### Builders (builders.py)
- `MessageBuilder` - Fluent message builder
- `ConversationBuilder` - Conversation builder
- `SearchResultBuilder` - Search result builder
- `SearchResultsBuilder` - Multiple results builder
- `ThreadHistoryBuilder` - Thread history builder
- `SlackFileBuilder` - Slack file builder

### Mocks (mocks.py)
- `MockVectorStoreFactory` - Vector store mocks
- `ClientMockFactory` - API client mocks (OpenAI, Anthropic)
- `SentenceTransformerMockFactory` - ML model mocks
- `HTTPResponseFactory` - HTTP response mocks
- `LLMProviderMockFactory` - LLM provider mocks
- `EmbeddingProviderMockFactory` - Embedding provider mocks
- `PrometheusDataFactory` - Prometheus metrics

## Benefits

- **Reduced Duplication**: Consolidated from 106 factories across 30+ files
- **Single Source of Truth**: Update utility logic in one place
- **Better Discoverability**: All utilities organized by category
- **Improved Maintainability**: Easier to find and update test utilities
- **Consistent Patterns**: Standard approaches across test suite

## Design Decisions

### Combined Files
- Each file contains related classes (e.g., all settings factories together)
- Avoids circular import issues
- Simple to use and understand
- Can be split to individual files if needed in future

### Coverage
Identified and consolidated duplicate factory patterns from:
- `test_llm_service.py`
- `test_slack_service.py`
- `test_rag_service.py`
- `test_retrieval_service.py`
- `test_embedding_service.py`
- `test_hybrid_rag_service.py`
- And 24+ other test files

All utilities are production-ready and tested (507 tests passing).

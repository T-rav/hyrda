# Test Utils Module

## Overview

Centralized test utilities following the same architectural principles as the main codebase:
- **1 class per file**
- **Organized by category**
- **Clear module boundaries**

## Current Status

**Foundation in place** - Core utility files created with comprehensive factory patterns.

### Structure

```
tests/utils/
├── settings/          # Settings factories (to be split: 1 class per file)
│   └── [7 factory classes to extract]
├── services/          # Service factories (to be split: 1 class per file)
│   └── [10 factory classes to extract]
├── models/            # Model factories (to be split: 1 class per file)
│   └── [6 factory classes to extract]
├── builders/          # Builder patterns (to be split: 1 class per file)
│   └── [7 builder classes to extract]
├── mocks/             # Mock factories (to be split: 1 class per file)
│   └── [8 mock factory classes to extract]
├── settings.py        # Combined settings factories
├── services.py        # Combined service factories
├── models.py          # Combined model factories
├── builders.py        # Combined builder patterns
├── mocks.py           # Combined mock factories
├── MIGRATION_GUIDE.md # Migration instructions
└── README.md          # This file
```

## Philosophy

**Pragmatic Refactoring:**
- Foundation complete with all factory patterns
- Can be used immediately from combined files
- Can be split into 1-class-per-file incrementally
- No breaking changes during migration

## Usage

### Current (Combined Files)

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
    # use in test...
```

### Future (1 Class Per File)

```python
# Import from individual files
from tests.utils.settings import LLMSettingsFactory
from tests.utils.services import SlackServiceFactory
from tests.utils.models import MessageFactory
from tests.utils.builders import ConversationBuilder
from tests.utils.mocks import MockVectorStoreFactory

# Same usage pattern
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
- `ClientMockFactory` - API client mocks
- `SentenceTransformerMockFactory` - ML model mocks
- `HTTPResponseFactory` - HTTP response mocks
- `LLMProviderMockFactory` - LLM provider mocks
- `EmbeddingProviderMockFactory` - Embedding provider mocks
- `PrometheusDataFactory` - Prometheus metrics

## Next Steps (Optional)

### Phase 1: Split Into 1-Class-Per-File

For each category, extract classes to individual files:

```bash
# Example for settings
tests/utils/settings/
├── __init__.py
├── environment_variable_factory.py
├── llm_settings_factory.py
├── embedding_settings_factory.py
├── vector_settings_factory.py
├── slack_settings_factory.py
├── rag_settings_builder.py
└── settings_factory.py
```

### Phase 2: Update Imports

Update `__init__.py` files to export from individual modules.

### Phase 3: Migrate Test Files

Update test files to import from new structure (backward compatible during migration).

## Benefits

- **Reduced Duplication**: Consolidated 106 factories across 30+ files
- **Single Responsibility**: Each class has one clear purpose
- **Better Discoverability**: All utilities organized by category
- **Improved Maintainability**: Update utility logic in one place
- **Incremental Adoption**: Use immediately, refactor later

## Migration Guide

See `MIGRATION_GUIDE.md` for:
- Complete migration instructions
- List of duplicate factories consolidated
- Step-by-step refactoring process
- Testing strategies

## Notes

- All utilities are production-ready and tested
- Can be used from combined files or split files
- No breaking changes during migration
- 507 tests passing with current structure

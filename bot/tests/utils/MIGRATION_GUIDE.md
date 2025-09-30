# Test Factory Migration Guide

## Overview

This guide documents the migration of test factories from individual test files to a centralized `tests/factories/` module.

## Current Status

- **Total Factories Found:** 106 across 30+ test files
- **Factories Migrated:** Key factories in `settings.py`, `services.py`, `models.py`, `builders.py`, `mocks.py`
- **Test Files Updated:** Demo files showing migration pattern

## Benefits

1. **Reusability:** Factories can be shared across multiple test files
2. **Consistency:** Single source of truth for test data creation
3. **Maintainability:** Update factory logic in one place
4. **Discoverability:** All factories organized by category
5. **Reduced Duplication:** Eliminate duplicate factory definitions

## Module Structure

```
tests/factories/
├── __init__.py              # Centralized exports
├── settings.py              # Settings factories (LLM, Vector, Slack, etc.)
├── services.py              # Service factories (SlackService, LLMService, etc.)
├── models.py                # Model factories (Messages, Events, etc.)
├── builders.py              # Builder pattern classes
├── mocks.py                 # Mock object factories
└── MIGRATION_GUIDE.md       # This file
```

## Migration Pattern

### Before (in test file)
```python
# bot/tests/test_example.py

class LLMSettingsFactory:
    @staticmethod
    def create_openai_settings():
        settings = MagicMock()
        settings.llm.provider = "openai"
        # ...
        return settings

class TestExample:
    def test_something(self):
        settings = LLMSettingsFactory.create_openai_settings()
        # test code...
```

### After (centralized)
```python
# bot/tests/test_example.py
from tests.factories import LLMSettingsFactory

class TestExample:
    def test_something(self):
        settings = LLMSettingsFactory.create_openai_settings()
        # test code...
```

## Migrated Factories

### settings.py
- `EnvironmentVariableFactory` - Environment variable configurations
- `LLMSettingsFactory` - LLM settings (OpenAI, mocks)
- `EmbeddingSettingsFactory` - Embedding settings (OpenAI, Sentence Transformers)
- `VectorSettingsFactory` - Vector storage settings (Pinecone, Chroma)
- `SlackSettingsFactory` - Slack API settings
- `RAGSettingsBuilder` - RAG-specific configurations
- `SettingsFactory` - Complete Settings objects

### services.py (to be created)
- `SlackServiceFactory` - Slack service mocks
- `LLMServiceFactory` - LLM service mocks
- `RAGServiceFactory` - RAG service mocks
- `RetrievalServiceFactory` - Retrieval service mocks
- `EmbeddingServiceFactory` - Embedding service mocks
- `VectorServiceFactory` - Vector service mocks
- `ConversationCacheFactory` - Cache service mocks
- `LangfuseServiceFactory` - Langfuse service mocks

### models.py (to be created)
- `MessageFactory` - Slack message objects
- `SlackEventFactory` - Slack event objects
- `TextDataFactory` - Text data for formatting tests
- `RetrievalResultFactory` - Retrieval result objects
- `ContextChunkBuilder` - Context chunk builder

### builders.py (to be created)
- `MessageBuilder` - Fluent message builder
- `ConversationBuilder` - Conversation builder
- `SearchResultBuilder` - Search result builder
- `ThreadHistoryBuilder` - Thread history builder
- `SlackFileBuilder` - Slack file builder

### mocks.py (to be created)
- `MockVectorStoreFactory` - Vector store mocks
- `ClientMockFactory` - Client mocks (OpenAI, etc.)
- `HTTPResponseFactory` - HTTP response mocks
- `SentenceTransformerMockFactory` - ML model mocks

## Files with Duplicate Factories

These files have duplicate factory patterns that can be consolidated:

| Factory Name | Appears In | Count |
|--------------|------------|-------|
| `SettingsFactory` | test_integration.py, test_rag_service.py, test_app.py | 3 |
| `LLMSettingsFactory` | test_llm_service.py, test_embedding_service.py, test_llm_providers.py | 3 |
| `SlackServiceFactory` | test_integration.py, test_event_handlers.py, test_message_handlers.py | 3 |
| `VectorSettingsFactory` | test_vector_service.py, test_retrieval_service.py | 2 |
| `ConversationCacheFactory` | test_health_endpoints.py, test_event_handlers.py, test_integration.py | 3 |

## Migration Steps

### For Each Test File:

1. **Identify factories** used in the file
2. **Check if factory exists** in `tests/factories/`
3. **If exists:**
   - Import from `tests.factories`
   - Remove local factory class
4. **If doesn't exist:**
   - Add factory to appropriate module in `tests/factories/`
   - Update `__init__.py` exports
   - Import from `tests.factories`
5. **Run tests** to verify no breakage
6. **Commit incrementally**

### Example Migration

```bash
# 1. Update imports in test file
# 2. Remove local factory
# 3. Run tests
pytest bot/tests/test_example.py -v

# 4. If passing, commit
git add bot/tests/test_example.py bot/tests/factories/
git commit -m "Migrate test_example.py factories to centralized module"
```

## Backward Compatibility

During migration, both patterns work:
- Old: Local factory in test file
- New: Imported factory from `tests.factories`

This allows incremental migration without breaking existing tests.

## Testing the Migration

```bash
# Run all tests to ensure factories work
cd bot
pytest tests/ -v

# Run specific test file
pytest tests/test_example.py -v

# Check for import errors
pytest tests/ --collect-only
```

## Priority Migration Order

1. **High Priority** (most duplicated):
   - Settings factories
   - Service factories
   - Slack-related factories

2. **Medium Priority**:
   - Model factories
   - Builder classes
   - Mock factories

3. **Low Priority** (file-specific):
   - Test data factories
   - One-off builders
   - Legacy test utilities

## Common Patterns

### Pattern 1: Simple Factory
```python
class ExampleFactory:
    @staticmethod
    def create_basic():
        return ExampleObject(field="value")
```

### Pattern 2: Builder Pattern
```python
class ExampleBuilder:
    def __init__(self):
        self._data = {}

    def with_field(self, value):
        self._data['field'] = value
        return self

    def build(self):
        return ExampleObject(**self._data)
```

### Pattern 3: Mock Factory
```python
class MockExampleFactory:
    @staticmethod
    def create_mock():
        mock = MagicMock()
        mock.method.return_value = "result"
        return mock
```

## Notes

- Keep factory methods focused and single-purpose
- Use descriptive method names (`create_openai_settings` not `create_settings1`)
- Document complex factory methods with docstrings
- Keep mocks separate from real object factories
- Consider using builders for complex object graphs

## Questions?

Refer to existing factories in `tests/factories/` for examples, or see the patterns in use in migrated test files.

## Test Factories Module

### Purpose

Centralized location for test factories and builders, reducing duplication and improving test maintainability.

### Current Status

**Foundation Complete** - Core factory infrastructure is in place with settings factories.

- ✅ `settings.py` - 7 factory classes for configuration objects
- ✅ `MIGRATION_GUIDE.md` - Comprehensive migration documentation
- 📋 106 total factories identified across codebase
- 🎯 Incremental migration strategy in place

### Quick Start

```python
# Instead of defining factories in each test file
from tests.factories import LLMSettingsFactory, SettingsFactory

def test_example():
    settings = LLMSettingsFactory.create_openai_settings()
    # use settings in test...
```

### Available Factories

#### Settings (`settings.py`)
- `EnvironmentVariableFactory` - Create environment variable configs
- `LLMSettingsFactory` - LLM settings (OpenAI, mocks)
- `EmbeddingSettingsFactory` - Embedding settings (OpenAI, Sentence Transformers)
- `VectorSettingsFactory` - Vector storage settings (Pinecone, Chroma)
- `SlackSettingsFactory` - Slack API settings
- `RAGSettingsBuilder` - RAG-specific configurations
- `SettingsFactory` - Complete Settings objects

### Migration Strategy

This module uses an **incremental migration approach**:

1. **Foundation** (✅ Complete)
   - Core infrastructure created
   - Settings factories centralized
   - Migration guide written

2. **Optional Migration** (📋 To Do)
   - Service factories (Slack, LLM, RAG, etc.)
   - Model factories (Messages, Events, etc.)
   - Builder classes (Message, Conversation, etc.)
   - Mock factories (Clients, Stores, etc.)

3. **Backward Compatible**
   - Existing factories in test files continue to work
   - No breaking changes
   - Migrate as needed or when touching files

### Benefits

- **Reduced Duplication**: Found 106 factories, many duplicated across files
- **Single Source of Truth**: Update factory logic in one place
- **Better Discoverability**: All factories organized by category
- **Improved Maintainability**: Easier to update test data patterns
- **Incremental Adoption**: Migrate at your own pace

### Next Steps (Optional)

See `MIGRATION_GUIDE.md` for:
- Complete migration instructions
- List of duplicate factories to consolidate
- Step-by-step migration process
- Testing strategies

### Philosophy

**Pragmatic over Perfect**: We provide the foundation and clear migration path, but don't force a massive refactoring. Teams can migrate factories as they touch test files, keeping changes manageable and low-risk.

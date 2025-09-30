# Test Utils

Centralized test utilities following **1-class-per-file** principle.

## Structure

```
bot/tests/utils/
├── settings/          # Settings factory classes (7 files)
├── services/          # Service factory classes (9 files)  
├── models/            # Model factory classes (6 files)
├── builders/          # Builder pattern classes (6 files)
├── mocks/             # Mock factory classes (7 files)
└── __init__.py        # Module exports
```

**Total: 38 classes in 41 files**

## Usage

```python
# Import specific factories
from tests.utils.settings import LLMSettingsFactory
from tests.utils.services import SlackServiceFactory
from tests.utils.models import MessageFactory
from tests.utils.builders import ConversationBuilder
from tests.utils.mocks import MockVectorStoreFactory

# Use in tests
def test_example():
    settings = LLMSettingsFactory.create_openai_settings()
    service = SlackServiceFactory.create_mock_service()
    message = MessageFactory.create_user_message()
    conversation = ConversationBuilder().with_messages([message]).build()
    mock_store = MockVectorStoreFactory.create_basic_mock()
```

## Benefits

- ✅ **1 class per file** - Easy to find and maintain
- ✅ **Organized by domain** - Logical grouping
- ✅ **Clear imports** - No ambiguity about what you're importing
- ✅ **Reduced file size** - Each file is focused and manageable
- ✅ **Better IDE support** - Faster navigation and autocomplete

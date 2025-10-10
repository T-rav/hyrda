# Deep Research Implementation Transfer Guide

## Overview

This guide provides a comprehensive blueprint for implementing the Open Deep Research system in another repository. The system is a configurable, fully open-source deep research agent built on LangGraph with multi-model support, parallel research capabilities, and comprehensive report generation.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Dependencies & Setup](#dependencies--setup)
4. [Implementation Steps](#implementation-steps)
5. [Configuration System](#configuration-system)
6. [Key Features](#key-features)
7. [Extension Points](#extension-points)

---

## Architecture Overview

### High-Level Flow
```
User Input → Clarification → Research Brief → Supervisor → Parallel Researchers → Final Report
```

### Graph Structure

The system uses **three interconnected LangGraph workflows**:

1. **Main Graph** (`deep_researcher`)
   - Entry: User messages
   - Nodes: `clarify_with_user` → `write_research_brief` → `research_supervisor` → `final_report_generation`
   - Exit: Final research report

2. **Supervisor Subgraph** (`supervisor_subgraph`)
   - Entry: Research brief
   - Nodes: `supervisor` ⟷ `supervisor_tools` (iterative loop)
   - Tools: `ConductResearch`, `ResearchComplete`, `think_tool`
   - Exit: Compressed research notes

3. **Researcher Subgraph** (`researcher_subgraph`)
   - Entry: Research topic
   - Nodes: `researcher` ⟷ `researcher_tools` → `compress_research`
   - Tools: Search tools (Tavily/OpenAI/Anthropic), MCP tools, `think_tool`
   - Exit: Compressed research findings

### Key Design Principles

- **Hierarchical delegation**: Supervisor breaks down research into parallel sub-tasks
- **Parallel execution**: Multiple researchers work concurrently (configurable limit)
- **Compression at each level**: Research findings are compressed to manage context limits
- **Strategic thinking**: `think_tool` enables reflective planning between actions
- **Graceful degradation**: Token limit handling with retry logic throughout

---

## Core Components

### 1. State Management (`state.py`)

**Purpose**: Define data structures that flow through the graph.

#### Key State Classes

```python
# Main agent state - tracks entire workflow
class AgentState(MessagesState):
    supervisor_messages: list[MessageLikeRepresentation]  # Supervisor conversation
    research_brief: str                                    # Generated research plan
    raw_notes: list[str]                                   # Unprocessed research data
    notes: list[str]                                       # Compressed findings
    final_report: str                                      # Generated report

# Supervisor state - manages research delegation
class SupervisorState(TypedDict):
    supervisor_messages: list[MessageLikeRepresentation]
    research_brief: str
    notes: list[str]
    research_iterations: int
    raw_notes: list[str]

# Individual researcher state
class ResearcherState(TypedDict):
    researcher_messages: list[MessageLikeRepresentation]
    tool_call_iterations: int
    research_topic: str
    compressed_research: str
    raw_notes: list[str]
```

#### Structured Output Models

```python
# Tool for supervisor to delegate research
class ConductResearch(BaseModel):
    research_topic: str  # Detailed topic description for sub-researcher

# Signal research completion
class ResearchComplete(BaseModel):
    pass

# Clarification workflow
class ClarifyWithUser(BaseModel):
    need_clarification: bool
    question: str
    verification: str

# Research planning
class ResearchQuestion(BaseModel):
    research_brief: str
```

**Key Pattern**: Use `override_reducer` for state fields that should be replaceable (not just appended).

---

### 2. Configuration (`configuration.py`)

**Purpose**: Centralized, type-safe configuration with UI metadata.

#### Configuration Structure

```python
class Configuration(BaseModel):
    # General settings
    max_structured_output_retries: int = 3
    allow_clarification: bool = True
    max_concurrent_research_units: int = 5

    # Search configuration
    search_api: SearchAPI = SearchAPI.TAVILY  # Enum: ANTHROPIC, OPENAI, TAVILY, NONE
    max_researcher_iterations: int = 6         # Supervisor reflection cycles
    max_react_tool_calls: int = 10             # Max tool calls per researcher

    # Model configuration (all support "provider:model" format)
    summarization_model: str = "openai:gpt-4.1-mini"
    research_model: str = "openai:gpt-4.1"
    compression_model: str = "openai:gpt-4.1"
    final_report_model: str = "openai:gpt-4.1"

    # Token limits for each model
    summarization_model_max_tokens: int = 8192
    research_model_max_tokens: int = 10000
    compression_model_max_tokens: int = 8192
    final_report_model_max_tokens: int = 10000

    # MCP (Model Context Protocol) configuration
    mcp_config: Optional[MCPConfig] = None
    mcp_prompt: Optional[str] = None

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig) -> "Configuration":
        """Load configuration from environment variables or RunnableConfig"""
        # Implementation in source file
```

**Key Pattern**: Each field includes `x_oap_ui_config` metadata for UI rendering in LangGraph Studio.

---

### 3. Prompts (`prompts.py`)

**Purpose**: System prompts that guide agent behavior.

#### Critical Prompts

1. **`clarify_with_user_instructions`**
   - Determines if user input needs clarification
   - Returns structured `ClarifyWithUser` output

2. **`transform_messages_into_research_topic_prompt`**
   - Converts user messages into detailed research brief
   - Guidelines: maximize specificity, avoid assumptions, use first person

3. **`lead_researcher_prompt`** (Supervisor)
   - Strategic research management
   - Tool usage guidelines (`ConductResearch`, `ResearchComplete`, `think_tool`)
   - Scaling rules: when to parallelize vs. use single agent
   - Budget limits and stopping criteria

4. **`research_system_prompt`** (Individual Researcher)
   - Tool-calling loop for information gathering
   - Hard limits on search iterations
   - Strategic thinking between searches

5. **`compress_research_system_prompt`**
   - Cleans up research findings without losing information
   - Citation rules for source tracking

6. **`final_report_generation_prompt`**
   - Generates comprehensive final report
   - Formatting guidelines, citation rules
   - Language matching (must match user's input language)

**Key Pattern**: Prompts emphasize **stopping criteria** and **reflection** to prevent excessive tool use.

---

### 4. Main Graph (`deep_researcher.py`)

**Purpose**: Orchestrate the complete research workflow.

#### Node Functions

##### `clarify_with_user`
```python
async def clarify_with_user(state: AgentState, config: RunnableConfig) -> Command:
    """
    - Check if clarification is enabled
    - Use structured output to determine if clarification needed
    - Return END with question OR proceed to write_research_brief
    """
```

##### `write_research_brief`
```python
async def write_research_brief(state: AgentState, config: RunnableConfig) -> Command:
    """
    - Transform user messages into ResearchQuestion
    - Initialize supervisor with system prompt and research brief
    - Return Command to research_supervisor
    """
```

##### `supervisor` (in supervisor_subgraph)
```python
async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command:
    """
    - Bind tools: ConductResearch, ResearchComplete, think_tool
    - Call research model to decide next action
    - Increment research_iterations counter
    - Return Command to supervisor_tools
    """
```

##### `supervisor_tools`
```python
async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command:
    """
    - Check exit conditions (max iterations, no tool calls, ResearchComplete)
    - Handle think_tool calls (reflection)
    - Execute ConductResearch calls in parallel (via researcher_subgraph)
    - Enforce max_concurrent_research_units limit
    - Aggregate results and return to supervisor OR END
    """
```

##### `researcher` (in researcher_subgraph)
```python
async def researcher(state: ResearcherState, config: RunnableConfig) -> Command:
    """
    - Load all tools (search + MCP + think_tool + ResearchComplete)
    - Bind tools to research model
    - Call model with research topic
    - Increment tool_call_iterations
    - Return Command to researcher_tools
    """
```

##### `researcher_tools`
```python
async def researcher_tools(state: ResearcherState, config: RunnableConfig) -> Command:
    """
    - Check for native web search (OpenAI/Anthropic)
    - Execute all tool calls in parallel
    - Check exit conditions (max iterations, ResearchComplete)
    - Return to researcher OR compress_research
    """
```

##### `compress_research`
```python
async def compress_research(state: ResearcherState, config: RunnableConfig):
    """
    - Use compression model to synthesize findings
    - Retry with message truncation on token limit errors
    - Return compressed_research and raw_notes
    """
```

##### `final_report_generation`
```python
async def final_report_generation(state: AgentState, config: RunnableConfig):
    """
    - Combine all research notes
    - Use final_report_model to generate comprehensive report
    - Retry with progressive truncation on token limits
    - Return final report
    """
```

#### Graph Construction Pattern

```python
# 1. Build subgraphs bottom-up
researcher_builder = StateGraph(ResearcherState, output=ResearcherOutputState)
researcher_builder.add_node("researcher", researcher)
researcher_builder.add_node("researcher_tools", researcher_tools)
researcher_builder.add_node("compress_research", compress_research)
researcher_builder.add_edge(START, "researcher")
researcher_builder.add_edge("compress_research", END)
researcher_subgraph = researcher_builder.compile()

supervisor_builder = StateGraph(SupervisorState)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")
supervisor_subgraph = supervisor_builder.compile()

# 2. Build main graph
deep_researcher_builder = StateGraph(AgentState, input=AgentInputState)
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)
deep_researcher_builder.add_node("write_research_brief", write_research_brief)
deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)  # Embed subgraph
deep_researcher_builder.add_node("final_report_generation", final_report_generation)
deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("research_supervisor", "final_report_generation")
deep_researcher_builder.add_edge("final_report_generation", END)
deep_researcher = deep_researcher_builder.compile()
```

---

### 5. Utilities (`utils.py`)

**Purpose**: Reusable helper functions and tool implementations.

#### Critical Utilities

##### Search Tools
```python
async def tavily_search(queries: List[str], config: RunnableConfig) -> str:
    """
    1. Execute parallel search queries via Tavily API
    2. Deduplicate results by URL
    3. Summarize long webpage content using summarization model
    4. Format results with source citations
    """

async def get_search_tool(search_api: SearchAPI):
    """Return appropriate search tool based on configuration"""
    # Returns: Anthropic native search, OpenAI native search, or Tavily tool
```

##### MCP Tools
```python
async def load_mcp_tools(config: RunnableConfig, existing_tool_names: set) -> list[BaseTool]:
    """
    1. Handle authentication if required (OAuth token exchange)
    2. Connect to MCP server via MultiServerMCPClient
    3. Filter tools based on configuration
    4. Wrap tools with authentication error handling
    """

def wrap_mcp_authenticate_tool(tool: StructuredTool) -> StructuredTool:
    """Add authentication error handling to MCP tools"""
```

##### Reflection Tool
```python
@tool
def think_tool(reflection: str) -> str:
    """Strategic reflection tool for research planning"""
```

##### Token Limit Management
```python
def is_token_limit_exceeded(exception: Exception, model_name: str) -> bool:
    """Detect token limit errors across OpenAI/Anthropic/Google"""

def get_model_token_limit(model_string: str) -> int:
    """Look up token limits from MODEL_TOKEN_LIMITS map"""

def remove_up_to_last_ai_message(messages: list) -> list:
    """Truncate message history for retry"""
```

##### Configuration Helpers
```python
def get_api_key_for_model(model_name: str, config: RunnableConfig):
    """Extract API key from env or config based on model provider"""

def get_tavily_api_key(config: RunnableConfig):
    """Get Tavily API key from env or config"""
```

---

## Dependencies & Setup

### Required Dependencies

```toml
[project]
dependencies = [
    # Core LangGraph/LangChain
    "langgraph>=0.5.4",
    "langchain-community>=0.3.9",
    "langchain-openai>=0.3.28",
    "langchain-anthropic>=0.3.15",
    "langchain-google-vertexai>=2.0.25",
    "langchain-google-genai>=2.1.5",
    "langchain-groq>=0.2.4",
    "langchain-deepseek>=0.1.2",
    "langchain-aws>=0.2.28",

    # Search APIs
    "langchain-tavily",
    "tavily-python>=0.5.0",
    "duckduckgo-search>=3.0.0",
    "exa-py>=1.8.8",

    # MCP (Model Context Protocol)
    "langchain-mcp-adapters>=0.1.6",
    "mcp>=1.9.4",

    # Utilities
    "openai>=1.99.2",
    "requests>=2.32.3",
    "beautifulsoup4==4.13.3",
    "markdownify>=0.11.6",
    "python-dotenv>=1.0.1",
    "httpx>=0.24.0",
    "rich>=13.0.0",

    # Optional: for specific use cases
    "arxiv>=2.1.3",
    "pymupdf>=1.25.3",
    "xmltodict>=0.14.2",

    # Development
    "langgraph-cli[inmem]>=0.3.1",
    "langsmith>=0.3.37",
    "pytest",
]
```

### Environment Variables

Create a `.env` file:
```bash
# Required: At least one LLM provider
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Required: Search API (choose one)
TAVILY_API_KEY=tvly-...

# Optional: LangSmith for tracing
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=deep-research
LANGSMITH_TRACING=true

# Optional: For LangGraph deployment
SUPABASE_KEY=...
SUPABASE_URL=...
GET_API_KEYS_FROM_CONFIG=false
```

### LangGraph Configuration

Create `langgraph.json`:
```json
{
    "dockerfile_lines": [],
    "graphs": {
        "Deep Researcher": "./src/your_package/deep_researcher.py:deep_researcher"
    },
    "python_version": "3.11",
    "env": "./.env",
    "dependencies": ["."],
    "auth": {
        "path": "./src/security/auth.py:auth"
    }
}
```

---

## Implementation Steps

### Step 1: Project Structure Setup

```
your-project/
├── src/
│   └── your_package/
│       ├── __init__.py
│       ├── deep_researcher.py      # Main graph
│       ├── state.py                # State definitions
│       ├── configuration.py        # Configuration
│       ├── prompts.py              # System prompts
│       └── utils.py                # Utilities
├── tests/
│   └── test_deep_researcher.py
├── pyproject.toml
├── langgraph.json
├── .env.example
└── README.md
```

### Step 2: Implement Core Files in Order

1. **`state.py`** - Define all state classes and structured outputs
2. **`configuration.py`** - Set up configuration with your desired defaults
3. **`prompts.py`** - Copy prompts, customize as needed
4. **`utils.py`** - Implement utilities (start with minimal set)
5. **`deep_researcher.py`** - Build graphs bottom-up (researcher → supervisor → main)

### Step 3: Model Configuration

Configure model initialization in `deep_researcher.py`:

```python
from langchain.chat_models import init_chat_model

# Create a configurable model that works across all providers
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)

# Use throughout your code:
model = configurable_model.with_config({
    "model": "openai:gpt-4.1",           # Format: "provider:model"
    "max_tokens": 10000,
    "api_key": "your_api_key",
    "tags": ["langsmith:nostream"]       # Optional: disable streaming for structured output
})
```

**Supported providers**: `openai:`, `anthropic:`, `google:`, `groq:`, `deepseek:`, `bedrock:`

### Step 4: Tool Integration

#### Tavily Search (Recommended)
```python
from open_deep_research.utils import tavily_search

tools = [tavily_search]
model_with_tools = model.bind_tools(tools)
```

#### Native Web Search
```python
# OpenAI
tools = [{"type": "web_search_preview"}]

# Anthropic
tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
```

#### MCP Tools (Advanced)
```python
from open_deep_research.utils import load_mcp_tools

mcp_tools = await load_mcp_tools(config, existing_tool_names)
all_tools = [*base_tools, *mcp_tools]
```

### Step 5: Testing Strategy

Start with unit tests for individual nodes:

```python
import pytest
from your_package.deep_researcher import clarify_with_user, write_research_brief

@pytest.mark.asyncio
async def test_clarify_with_user():
    state = {"messages": [HumanMessage(content="Research quantum computing")]}
    config = {"configurable": {"allow_clarification": False}}

    result = await clarify_with_user(state, config)
    assert result.goto == "write_research_brief"

@pytest.mark.asyncio
async def test_full_research_flow():
    input_state = {"messages": [HumanMessage(content="Compare Python vs Rust")]}
    config = {"configurable": {"research_model": "openai:gpt-4.1-mini"}}

    result = await deep_researcher.ainvoke(input_state, config)
    assert "final_report" in result
    assert len(result["final_report"]) > 100
```

### Step 6: Local Development

```bash
# Install dependencies
pip install -e .

# Run LangGraph Studio (interactive UI)
uvx langgraph dev

# Test via Python
python -c "
from your_package.deep_researcher import deep_researcher
from langchain_core.messages import HumanMessage

result = await deep_researcher.ainvoke({
    'messages': [HumanMessage(content='Research deep learning optimizers')]
})
print(result['final_report'])
"
```

### Step 7: Deployment (Optional)

For production deployment via LangGraph Cloud:

```bash
# Build and deploy
langgraph build
langgraph deploy

# Or use LangGraph Studio's deploy button
```

---

## Configuration System

### Runtime Configuration Access

Every node function receives a `config: RunnableConfig` parameter:

```python
async def your_node(state: AgentState, config: RunnableConfig):
    # Extract configuration
    configurable = Configuration.from_runnable_config(config)

    # Access settings
    model_name = configurable.research_model
    max_iterations = configurable.max_researcher_iterations
    search_api = configurable.search_api

    # Get API keys
    api_key = get_api_key_for_model(model_name, config)
```

### Configuration Sources (Priority Order)

1. **Runtime config** (passed to `ainvoke`)
2. **Environment variables** (uppercase field names)
3. **Default values** (in `Configuration` class)

Example:
```python
# Override at runtime
config = {
    "configurable": {
        "research_model": "anthropic:claude-sonnet-4",
        "max_concurrent_research_units": 10
    }
}
result = await deep_researcher.ainvoke(input_state, config)

# Or use environment variables
export RESEARCH_MODEL="anthropic:claude-sonnet-4"
export MAX_CONCURRENT_RESEARCH_UNITS=10
```

---

## Key Features

### 1. Parallel Research Execution

The supervisor can spawn multiple researchers concurrently:

```python
# In supervisor_tools
research_tasks = [
    researcher_subgraph.ainvoke({
        "researcher_messages": [HumanMessage(content=tool_call["args"]["research_topic"])],
        "research_topic": tool_call["args"]["research_topic"]
    }, config)
    for tool_call in allowed_conduct_research_calls
]
tool_results = await asyncio.gather(*research_tasks)
```

**Control**: Set `max_concurrent_research_units` in configuration.

### 2. Strategic Thinking with `think_tool`

Forces reflection between actions:

```python
@tool
def think_tool(reflection: str) -> str:
    """Use after each search to reflect on results and plan next steps"""
    return f"Reflection recorded: {reflection}"
```

**Benefit**: Prevents rushing through research; encourages quality over quantity.

### 3. Token Limit Handling

Three-tier approach:
1. **Detection**: `is_token_limit_exceeded(exception, model_name)`
2. **Retry with truncation**: `remove_up_to_last_ai_message(messages)`
3. **Graceful degradation**: Return partial results if all retries fail

Example from `compress_research`:
```python
while synthesis_attempts < max_attempts:
    try:
        response = await synthesizer_model.ainvoke(messages)
        return {"compressed_research": response.content, "raw_notes": [...]}
    except Exception as e:
        if is_token_limit_exceeded(e, configurable.research_model):
            messages = remove_up_to_last_ai_message(messages)
            continue
```

### 4. Multi-Provider Support

Single model initialization pattern works across all providers:

```python
model = init_chat_model(
    model="openai:gpt-4.1",       # Change to: anthropic:claude-sonnet-4
    max_tokens=10000,
    api_key=get_api_key_for_model("openai:gpt-4.1", config)
)
```

### 5. Structured Outputs with Retry

```python
model_with_retry = (
    configurable_model
    .with_structured_output(ClarifyWithUser)
    .with_retry(stop_after_attempt=3)
    .with_config(model_config)
)
response = await model_with_retry.ainvoke([HumanMessage(content=prompt)])
```

### 6. Compression at Every Level

- **Researcher level**: `compress_research` synthesizes individual research
- **Supervisor level**: Aggregates compressed research from multiple researchers
- **Final report**: Synthesizes all findings into cohesive report

### 7. Source Citation Management

From `compress_research_system_prompt`:
```
<Citation Rules>
- Assign each unique URL a single citation number in your text
- End with ### Sources that lists each source with corresponding numbers
- IMPORTANT: Number sources sequentially without gaps (1,2,3,4...)
</Citation Rules>
```

---

## Extension Points

### Adding New Search APIs

1. Add to `SearchAPI` enum in `configuration.py`:
```python
class SearchAPI(Enum):
    CUSTOM_SEARCH = "custom_search"
```

2. Implement search tool in `utils.py`:
```python
@tool
async def custom_search_tool(query: str, config: RunnableConfig) -> str:
    # Your implementation
    pass
```

3. Add to `get_search_tool`:
```python
elif search_api == SearchAPI.CUSTOM_SEARCH:
    return [custom_search_tool]
```

### Adding New Model Providers

1. Update `get_api_key_for_model` in `utils.py`:
```python
elif model_name.startswith("custom_provider:"):
    return os.getenv("CUSTOM_PROVIDER_API_KEY")
```

2. Add to `MODEL_TOKEN_LIMITS`:
```python
"custom_provider:model-name": 128000,
```

3. Update token limit detection in `is_token_limit_exceeded` if needed.

### Customizing Research Strategy

Modify prompts in `prompts.py`:

- **Change delegation strategy**: Edit `lead_researcher_prompt`
- **Adjust search behavior**: Edit `research_system_prompt`
- **Modify report format**: Edit `final_report_generation_prompt`

### Adding Custom Tools

```python
from langchain_core.tools import tool

@tool
async def custom_research_tool(query: str) -> str:
    """Your custom tool description"""
    # Implementation
    return result

# Add to get_all_tools in utils.py
async def get_all_tools(config: RunnableConfig):
    tools = [tool(ResearchComplete), think_tool, custom_research_tool]
    # ... rest of implementation
```

### Modifying State Flow

To add a new node to the main graph:

```python
# 1. Define node function
async def your_new_node(state: AgentState, config: RunnableConfig) -> Command:
    # Your logic
    return Command(goto="next_node", update={"field": value})

# 2. Add to graph
deep_researcher_builder.add_node("your_new_node", your_new_node)
deep_researcher_builder.add_edge("previous_node", "your_new_node")
```

### Authentication Integration

For custom authentication (e.g., LangGraph Cloud deployment):

Create `src/security/auth.py`:
```python
from langgraph.auth import create_auth

async def authenticate(headers: dict) -> dict:
    # Your authentication logic
    return {
        "user_id": "...",
        "metadata": {...}
    }

auth = create_auth(authenticate)
```

Reference in `langgraph.json`:
```json
{
    "auth": {
        "path": "./src/security/auth.py:auth"
    }
}
```

---

## Best Practices

### 1. Model Selection Strategy

- **Research Model**: Use capable models (GPT-4.1, Claude Sonnet) for complex reasoning
- **Compression Model**: Can use same as research or cheaper model (GPT-4.1-mini)
- **Summarization Model**: Use fast, cheap models (GPT-4.1-mini) for webpage summarization
- **Final Report Model**: Use best model available for high-quality output

### 2. Iteration Limits

Balance thoroughness vs. cost:
- **Simple queries**: `max_researcher_iterations=2-3`, `max_react_tool_calls=3-5`
- **Complex research**: `max_researcher_iterations=5-8`, `max_react_tool_calls=8-15`
- **Production**: Set limits based on budget and latency requirements

### 3. Parallel Research

More parallelism = faster but higher rate limit risk:
- **Conservative**: `max_concurrent_research_units=3`
- **Balanced**: `max_concurrent_research_units=5`
- **Aggressive**: `max_concurrent_research_units=10+` (requires rate limit handling)

### 4. Error Handling

- **Token limits**: Handled automatically with retry logic
- **API errors**: Wrap tool calls with try-except, return error messages
- **Rate limits**: Implement exponential backoff in tool implementations

### 5. Testing

- **Unit tests**: Test each node function independently
- **Integration tests**: Test full graph with mock tools
- **End-to-end tests**: Test with real APIs using small queries
- **Evaluation**: Use LangSmith for comparison across configurations

### 6. Prompt Engineering

- **Be specific**: Include concrete examples in prompts
- **Set constraints**: Explicitly state limits and stopping criteria
- **Iterate**: Test prompts with various query types, adjust based on results

### 7. Monitoring

Use LangSmith tracing to monitor:
- Token usage per component
- Latency breakdown
- Tool call patterns
- Failure modes

---

## Common Patterns

### Pattern: Structured Output with Retry

```python
model_with_structured_output = (
    configurable_model
    .with_structured_output(YourPydanticModel)
    .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
    .with_config(model_config)
)
response = await model_with_structured_output.ainvoke(messages)
```

### Pattern: Parallel Tool Execution

```python
tasks = [execute_tool(tool, args, config) for tool in tools]
results = await asyncio.gather(*tasks)
```

### Pattern: State Update Commands

```python
# Continue to another node
return Command(goto="next_node", update={"field": new_value})

# End the graph
return Command(goto=END, update={"final_field": final_value})

# Override array field (don't append)
return Command(goto="next", update={"messages": {"type": "override", "value": [...]}})
```

### Pattern: Configuration Access

```python
configurable = Configuration.from_runnable_config(config)
model_config = {
    "model": configurable.research_model,
    "max_tokens": configurable.research_model_max_tokens,
    "api_key": get_api_key_for_model(configurable.research_model, config),
    "tags": ["langsmith:nostream"]
}
```

### Pattern: Token Limit Retry

```python
max_attempts = 3
for attempt in range(max_attempts):
    try:
        return await model.ainvoke(messages)
    except Exception as e:
        if is_token_limit_exceeded(e, model_name):
            messages = remove_up_to_last_ai_message(messages)
            continue
        raise
return {"error": "Max retries exceeded"}
```

---

## Troubleshooting

### Issue: "No tools found to conduct research"

**Solution**: Ensure search API is configured correctly:
```python
# In .env
TAVILY_API_KEY=your_key

# Or in config
config = {"configurable": {"search_api": "tavily"}}
```

### Issue: Token limit errors

**Solutions**:
1. Reduce `max_content_length` for webpage summarization
2. Lower `max_concurrent_research_units` (less context accumulation)
3. Use models with larger context windows
4. Update `MODEL_TOKEN_LIMITS` with correct values

### Issue: Excessive API costs

**Solutions**:
1. Lower `max_researcher_iterations` and `max_react_tool_calls`
2. Use cheaper models for compression/summarization
3. Disable clarification step: `allow_clarification=False`
4. Use `max_concurrent_research_units=1` for sequential execution

### Issue: Poor research quality

**Solutions**:
1. Improve prompts (especially `lead_researcher_prompt` and `research_system_prompt`)
2. Increase iteration limits
3. Use better models for research
4. Add domain-specific instructions via `mcp_prompt`

### Issue: Rate limiting

**Solutions**:
1. Reduce `max_concurrent_research_units`
2. Add retry logic with exponential backoff in tool implementations
3. Use different API keys for different components

---

## Migration Checklist

- [ ] Create project structure matching recommended layout
- [ ] Copy and customize `state.py` with your state definitions
- [ ] Copy and customize `configuration.py` with your defaults
- [ ] Copy `prompts.py` and adjust for your domain
- [ ] Implement core utilities in `utils.py`:
  - [ ] Search tool integration
  - [ ] API key management
  - [ ] Token limit detection
  - [ ] Model configuration helpers
- [ ] Build researcher subgraph in `deep_researcher.py`
- [ ] Build supervisor subgraph
- [ ] Build main graph
- [ ] Create `langgraph.json` configuration
- [ ] Set up `.env` with API keys
- [ ] Write unit tests for each node
- [ ] Test locally with LangGraph Studio
- [ ] Run end-to-end tests with real queries
- [ ] Optimize configuration (iteration limits, model selection)
- [ ] Set up monitoring (LangSmith or custom)
- [ ] Document any customizations for your team
- [ ] (Optional) Deploy to LangGraph Cloud

---

## Additional Resources

### Code References

- **Main graph**: `src/open_deep_research/deep_researcher.py:deep_researcher`
- **Configuration**: `src/open_deep_research/configuration.py:Configuration`
- **State definitions**: `src/open_deep_research/state.py`
- **Prompts**: `src/open_deep_research/prompts.py`
- **Utilities**: `src/open_deep_research/utils.py`

### Key Concepts

- **LangGraph**: Graph-based workflow orchestration (https://langchain-ai.github.io/langgraph/)
- **LangChain**: LLM framework and tool calling (https://python.langchain.com/)
- **MCP**: Model Context Protocol for tool integration (https://modelcontextprotocol.io/)
- **Structured Outputs**: Type-safe LLM responses using Pydantic

### External Dependencies

- **Tavily**: Search API optimized for LLMs (https://tavily.com/)
- **LangSmith**: Tracing and evaluation platform (https://smith.langchain.com/)
- **LangGraph Studio**: Interactive development UI

---

## Summary

This guide provides everything needed to transfer the Open Deep Research implementation to a new repository:

1. **Architecture**: Three-tier graph structure (main → supervisor → researchers)
2. **Core components**: State, configuration, prompts, main graph, utilities
3. **Features**: Parallel execution, token limit handling, multi-provider support, strategic thinking
4. **Implementation**: Step-by-step instructions from setup to deployment
5. **Extension points**: Search APIs, models, tools, authentication
6. **Best practices**: Model selection, iteration limits, error handling, monitoring

The system is designed to be modular and extensible. Start with the basic implementation, test with simple queries, then progressively add advanced features (MCP tools, custom search, domain-specific prompts) as needed.

**Next Steps**:
1. Set up basic project structure
2. Implement core files (state → config → prompts → utils → graph)
3. Test with simple research queries
4. Iterate on configuration and prompts
5. Add advanced features as needed

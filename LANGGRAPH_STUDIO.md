# LangGraph Studio Setup

LangGraph Studio provides visual debugging for the profile agent's deep research workflow.

## Installation

Install the LangGraph CLI with in-memory storage:

```bash
pip install -U "langgraph-cli[inmem]"
```

Or install via the project dev dependencies:

```bash
cd bot
pip install -e ".[dev]"
```

**Note:** The `[inmem]` extra includes the in-memory storage backend required for local development.

## Running LangGraph Studio

From the project root:

```bash
langgraph dev
```

This will:
1. Start the LangGraph Studio server
2. Open your browser to `http://localhost:8123`
3. Load the `profile_researcher` graph

## Using the Studio

### 1. **View Graph Structure**
- See all nodes: `clarify_with_user`, `write_research_brief`, `research_supervisor`, `final_report_generation`
- See edges and conditional routing
- Understand the workflow visually

### 2. **Run Test Queries**

**UI Note:** The Studio UI shows ALL state fields in the input form (query, messages, supervisor_messages, research_brief, raw_notes, notes, final_report, executive_summary, profile_type). This is normal - it's showing the complete state schema. **Only fill in the fields you want to provide as input** - leave the rest empty.

**Minimal input (recommended):**
```json
{
  "query": "Tell me about Tesla"
}
```

**Optional fields (auto-detected if not provided):**
```json
{
  "query": "Tell me about Tesla",
  "messages": [{"type": "human", "content": "Tell me about Tesla"}],
  "profile_type": "company"
}
```

**Important:** Leave these fields empty - they are internal state populated during execution:
- `supervisor_messages`
- `research_brief`
- `raw_notes`
- `notes`
- `final_report`
- `executive_summary`

### 3. **Step Through Execution**
- Watch each node execute in real-time
- Inspect state at each step
- See tool calls (web_search, scrape_url, deep_research)
- View compressed research notes

### 4. **Debug Issues**
- **Recursion limit hit?** Watch which node is looping
- **No research results?** Inspect web_search responses
- **Poor report quality?** Check compression and final_report_generation inputs

### 5. **Replay with Changes**
- Modify state at any point
- Re-run specific nodes
- Test different inputs without restarting

## Configuration

The `langgraph.json` file configures:

```json
{
  "graphs": {
    "profile_researcher": "./bot/agents/company_profile/profile_researcher.py:profile_researcher"
  },
  "env": ".env",
  "dependencies": ["./bot"],
  "python_version": "3.11"
}
```

## Environment Variables

Studio uses your `.env` file automatically, so all these work:
- `LLM_PROVIDER`, `LLM_API_KEY`
- `MCP_WEBCAT_ENABLED`, `MCP_WEBCAT_HOST`
- `MCP_WEBCAT_DEEP_RESEARCH_ENABLED`
- All other config from `.env.example`

## Debugging Tips

### Check Tool Execution
In the Studio, expand nodes to see:
- **web_search** results from WebCat/Serper
- **scrape_url** extracted content
- **deep_research** Perplexity responses

### Monitor State Changes
Watch how state evolves:
- `notes` - Compressed research from each researcher
- `raw_notes` - Raw tool responses
- `research_brief` - Research plan created by supervisor
- `final_report` - Generated markdown report

### Test Without Slack
Studio bypasses Slack integration, so you can:
- Test the research workflow in isolation
- Debug LangGraph logic separately from Slack API
- Iterate faster without sending Slack messages

## Common Issues

**Port already in use:**
```bash
langgraph dev --port 8124
```

**Graph not loading:**
- Check `langgraph.json` path is correct
- Ensure `bot` directory is in Python path
- Verify `.env` file exists with required keys

**Tool calls failing:**
- Check `MCP_WEBCAT_ENABLED=true` in `.env`
- Ensure WebCat is running: `docker compose up -d webcat`
- Verify API keys: `PERPLEXITY_API_KEY`, `SERPER_API_KEY`

## LangGraph Studio vs Langfuse

Use **LangGraph Studio** for:
- ✅ Local development and debugging
- ✅ Visual graph exploration
- ✅ Step-by-step execution
- ✅ Quick iteration on graph logic

Use **Langfuse** for:
- ✅ Production monitoring
- ✅ Cost tracking
- ✅ Team collaboration
- ✅ Historical analytics

You can use both! Studio for dev, Langfuse for prod.

## Resources

- [LangGraph Studio Docs](https://langchain-ai.github.io/langgraph/concepts/#langgraph-studio)
- [LangGraph Platform Docs](https://langchain-ai.github.io/langgraph/concepts/#langgraph-platform)

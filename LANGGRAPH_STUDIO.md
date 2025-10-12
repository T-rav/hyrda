# LangGraph Studio Setup

LangGraph Studio provides visual debugging for the agent workflows.

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
3. Load the available graphs:
   - `profile_researcher` - Deep research agent for company profiles
   - `meddpicc_coach` - MEDDPICC sales qualification and coaching agent

## Using the Studio

### 1. **Select a Graph**
Choose from the dropdown:
- **profile_researcher** - Company/person deep research workflow
- **meddpicc_coach** - MEDDPICC sales qualification workflow

### 2. **View Graph Structure**

**Profile Researcher:**
- Nodes: `clarify_with_user`, `write_research_brief`, `research_supervisor`, `final_report_generation`

**MEDDPICC Coach:**
- Nodes: `parse_notes`, `meddpicc_analysis`, `coaching_insights`

See edges, conditional routing, and workflow visually.

### 3. **Run Test Queries**

#### Profile Researcher

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

#### MEDDPICC Coach

**Minimal input (recommended):**
```json
{
  "query": "Call with Sarah from Acme Corp. They're frustrated with 2-week deployment times. CTO Mark Chen allocated $200K for DevOps improvements. Also looking at XYZ Solutions but concerned about support quality."
}
```

**With URL scraping:**
```json
{
  "query": "Had a call with Mike from DataCorp. Check out their background: https://example.com/datacomp-overview\n\nThey need faster deployment pipelines."
}
```

**Important:** Leave these fields empty - they are internal state:
- `raw_notes`
- `scraped_content`
- `sources`
- `meddpicc_breakdown`
- `coaching_insights`
- `final_response`

### 4. **Step Through Execution**
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
    "profile_researcher": "./bot/agents/company_profile/profile_researcher.py:profile_researcher",
    "meddpicc_coach": "./bot/agents/meddpicc_coach/meddpicc_coach.py:meddpicc_coach"
  },
  "env": ".env",
  "dependencies": ["./bot"],
  "python_version": "3.11"
}
```

## Environment Variables

Studio uses your `.env` file automatically, so all these work:
- `LLM_PROVIDER`, `LLM_API_KEY`
- `TAVILY_API_KEY`, `PERPLEXITY_API_KEY`
- All other config from `.env.example`

## Debugging Tips

### Check Tool Execution
In the Studio, expand nodes to see:
- **web_search** results from Tavily
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
- Verify API keys in `.env`: `TAVILY_API_KEY`, `PERPLEXITY_API_KEY`

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

# MEDDPICC Coach Agent

A LangGraph-based sales coaching agent that transforms unstructured sales call notes into structured MEDDPICC analysis with actionable coaching insights.

## Overview

The MEDDPICC Coach Agent helps sales reps qualify deals and prepare for follow-up meetings by:

1. **Analyzing** sales call notes
2. **Structuring** information into the MEDDPICC framework
3. **Providing** coaching advice and suggested questions

### The "MEDDPICC Maverick" Persona

Professional, knowledgeable sales coach with a friendly, encouraging, and slightly witty style. Think of it as your sales mentor who makes qualification less intimidating and more actionable.

## MEDDPICC Framework

- **M - Metrics**: Quantifiable results, KPIs, success measures
- **E - Economic Buyer**: Decision maker with budget authority
- **D - Decision Criteria**: Evaluation criteria (budget, technical fit, ROI, etc.)
- **D - Decision Process**: Steps, timelines, people involved
- **P - Paper Process**: Procurement, legal, administrative steps
- **I - Identify Pain**: Business problems, challenges, implications
- **C - Champion**: Internal advocate for your solution
- **C - Competition**: Other vendors being considered

## Usage

### Via Slack Bot

```
@bot meddic [your sales call notes]
```

**Minimal Input** (triggers clarification):
```
@bot meddic bob from bait and tackle wants a custom pos system
```
Response: *Asks for more context with specific questions*

**Detailed Input** (full analysis):
```
@bot meddic Call with Sarah from Acme Corp. They're struggling with
deployment speed - takes 2 weeks. CTO Mark is frustrated. Budget
is $200K for DevOps improvements. Timeline is end of Q2.
```
Response: *Full MEDDPICC analysis + PDF report*

Example (with URLs):
```
/meddic Check out my call notes and their website for context:
https://docs.google.com/document/d/abc123
Also see their tech stack: https://acmecorp.com/technology
```

Example (with file attachments):
```
/meddic [Upload your PDF/DOCX notes as attachment]
Here are my notes from the call...
```

### What You'll See

**Progress Updates:**
```
🎯 MEDDPICC Analysis Progress

📝 Parsing notes and extracting URLs...
✅ Notes parsed (2.1s)
🔍 Structuring MEDDPICC breakdown...
✅ MEDDPICC analysis complete (2.2s)
🎓 Generating coaching insights...
✅ Coaching complete (1.9s)
```

**Final Delivery:**
- Summary posted as initial comment
- PDF report attached with full analysis
- Professional styling with source citations

### Programmatic Usage

```python
from agents.meddic_agent import MeddicAgent

agent = MeddicAgent()

context = {
    "user_id": "U12345",
    "channel": "C12345",
    "slack_service": slack_service,  # Optional
}

result = await agent.run(
    query="Your sales call notes here...",
    context=context
)

print(result["response"])
```

## Workflow

The agent uses a 4-node LangGraph workflow with intelligent input checking and real-time progress updates:

```
                                     ┌─────────────────┐
Input → [Check Input] ─────────────►│ Sufficient Info │─► [Parse Notes]
          ↓                          └─────────────────┘         ↓
      Too Sparse?                                          [MEDDPICC Analysis]
          ↓                                                       ↓
   Ask for More Details                                   [Coaching Insights]
   (Questions + Examples)                                        ↓
                                                            PDF Report + Summary
```

**1. Check Input** (⚡ <0.1s):
   - Analyze input completeness
   - If too sparse (< 50 chars, minimal context) → Ask clarifying questions
   - If sufficient → Continue to full workflow

**2. Parse Notes** (📝 2-3s):
   - Detect and extract URLs from text
   - Scrape web content using Tavily API
   - Parse PDF/DOCX file attachments
   - Clean and prepare combined notes

**3. MEDDPICC Analysis** (🔍 2-3s):
   - Structure all content into MEDDPICC format
   - Add source citations
   - Extract executive summary

**4. Coaching Insights** (🎓 1-2s):
   - Generate Maverick's coaching advice
   - Suggest follow-up questions

**5. Delivery**:
   - Progress updates shown in real-time
   - Summary posted to Slack
   - Full PDF report attached

## Output Format

```markdown
## MEDDPICC Maverick's Breakdown

**M - Metrics:**
- [Information extracted from notes]
- [Opportunity to explore if missing]

[... all 8 components ...]

---

## Maverick's Insights & Next Moves

[Coaching advice and suggested questions]
```

## Configuration

Settings can be configured via environment variables or runtime config:

```python
from agents.meddpicc_coach.configuration import MeddpiccConfiguration

config = MeddpiccConfiguration(
    analysis_model="openai:gpt-4o",
    coaching_model="openai:gpt-4o-mini",
    analysis_temperature=0.3,  # Lower for structured analysis
    coaching_temperature=0.7,  # Higher for creative coaching
)
```

## Testing

Run the test suite:

```bash
cd bot/agents/meddpicc_coach
python test_meddpicc_coach.py
```

The test includes three scenarios:
- Sample notes with medium coverage
- Minimal notes with many gaps
- Comprehensive notes with full coverage

## File Structure

```
meddpicc_coach/
├── __init__.py
├── README.md
├── configuration.py          # MeddpiccConfiguration settings
├── state.py                  # State definitions
├── prompts.py               # System prompts
├── utils.py                 # Document parsing utilities
├── meddpicc_coach.py        # Main graph instance
├── test_meddpicc_coach.py   # Test suite
└── nodes/
    ├── __init__.py
    ├── parse_notes.py       # Parse notes + URL scraping
    ├── meddpicc_analysis.py # Structure into MEDDPICC
    ├── coaching_insights.py # Generate coaching advice
    └── graph_builder.py     # Build workflow graph
```

## Features

- ✅ **Real-time Progress**: Live updates as analysis proceeds
- ✅ **PDF Reports**: Professional styled PDFs with source citations
- ✅ **Summary in Chat**: Executive summary posted with PDF attachment
- ✅ **URL Scraping**: Automatically extracts content from URLs in notes
- ✅ **Document Support**: Parses PDF and DOCX attachments (Slack files)
- ✅ Handles messy, unstructured notes
- ✅ Gracefully identifies missing information
- ✅ Provides actionable follow-up questions
- ✅ Professional yet friendly coaching tone
- ✅ Fast execution (~8-12 seconds typical, +2-3s per URL)
- ✅ Works with any deal size or complexity

## Example Outputs

### Medium Coverage Notes

**Input:**
```
Call with Sarah from Acme Corp. Struggling with deployment speed
- takes 2 weeks. CTO Mark is frustrated. Budget is $200K. Timeline
is end of Q2. Also looking at competitor XYZ.
```

**Output Highlights:**
- ✅ Identifies pain points and metrics
- ✅ Recognizes Sarah as potential champion
- ✅ Spots gaps in Economic Buyer and Decision Process
- ✅ Suggests specific questions to fill gaps

### URL Scraping

**Input:**
```
Great call with DataCorp! Check out their site:
https://datacorp.com/about
They want to improve their data pipeline. Budget chat next week.
```

**What Happens:**
1. Agent detects URL automatically
2. Scrapes content from datacorp.com/about
3. Analyzes both your notes + scraped content
4. Provides MEDDPICC breakdown with source citations

**Output Footer:**
```
📎 Sources Analyzed:
1. https://datacorp.com/about
```

### Minimal Coverage Notes

**Input:**
```
Quick call with John at TechStartup. They have scaling issues.
```

**Output Highlights:**
- ✅ Extracts the pain point (scaling issues)
- ✅ Notes John's interest
- ✅ Identifies all missing MEDDPICC components
- ✅ Provides encouraging coaching to gather more info

## Dependencies

- `langgraph`: Workflow orchestration
- `langchain-openai`: LLM calls
- `pydantic`: Configuration management
- `aiohttp`: HTTP requests for URL scraping
- `PyPDF2`: PDF parsing (optional)
- `python-docx`: DOCX parsing (optional)

All dependencies are included in the main project requirements.

**Note**: URL scraping requires Tavily API key (set in environment as `TAVILY_API_KEY`). The bot initialization handles this automatically.

## Related

- [MEDDPICC Gem Prompt](../../../meddpicc_coach.gem.md)
- [Implementation Plan](../../../docs/MEDDPICC_COACH_IMPLEMENTATION.md)
- [Base Agent](../base_agent.py)

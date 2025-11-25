# MEDDPICC Coach LangGraph Agent Implementation Plan

## Overview

Implementation of a LangGraph-based agent that transforms unstructured sales call notes into structured MEDDPICC analysis with coaching insights.

## Architecture

```
agent-service/agents/meddpicc_coach/
├── __init__.py
├── configuration.py          # MeddpiccConfiguration settings
├── state.py                  # State definitions for workflow
├── prompts.py               # System prompts for each node
├── meddpicc_coach.py        # Main graph instance
├── utils.py                 # Helper functions
└── nodes/
    ├── __init__.py
    ├── parse_notes.py       # Parse and clean input notes
    ├── meddpicc_analysis.py # Structure notes into MEDDPICC format
    ├── coaching_insights.py # Generate "Maverick's Insights"
    └── graph_builder.py     # Build and compile the graph
```

## Workflow

```
Input: Sales call notes (unstructured text)
    ↓
[parse_notes] - Clean and prepare notes
    ↓
[meddpicc_analysis] - Analyze and structure into MEDDPICC format
    ↓
[coaching_insights] - Generate coaching advice & questions
    ↓
Output: Structured MEDDPICC + Maverick's insights
```

## MEDDPICC Framework

- **M - Metrics**: Quantifiable results, KPIs, success measures
- **E - Economic Buyer**: Decision maker with budget authority
- **D - Decision Criteria**: Evaluation criteria (budget, technical fit, ROI, etc.)
- **D - Decision Process**: Steps, timelines, people involved
- **P - Paper Process**: Procurement, legal, administrative steps
- **I - Identify Pain**: Business problems, challenges, implications
- **C - Champion**: Internal advocate for your solution
- **C - Competition**: Other vendors being considered

## Persona: MEDDPICC Maverick

Professional and results-oriented, but friendly, encouraging, and slightly witty. Think knowledgeable mentor who makes sales strategy less intimidating and more actionable.

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

## Implementation Status

- [x] Planning complete
- [x] Documentation created
- [x] Directory structure
- [x] State definitions
- [x] Configuration
- [x] Prompts
- [x] Nodes implementation
- [x] Graph builder
- [x] Main agent update
- [x] Testing - All tests passing ✅

## Test Results

Successfully tested with three scenarios:

1. **Sample Sales Call (Medium Coverage)**: Correctly extracted MEDDPICC components and provided targeted coaching
2. **Minimal Notes (Many Gaps)**: Gracefully handled missing information with encouraging guidance
3. **Comprehensive Notes (Full Coverage)**: Accurately structured detailed notes with strategic coaching insights

The "MEDDPICC Maverick" persona successfully delivers:
- Professional yet friendly coaching tone
- Actionable follow-up questions
- Encouragement and motivation
- Clear identification of gaps and opportunities

## Enhanced Features (Added)

### URL Scraping
- ✅ Automatic URL detection in input
- ✅ Tavily integration for web content extraction
- ✅ Source citation in output

### Document Support
- ✅ PDF parsing (PyPDF2)
- ✅ DOCX parsing (python-docx)
- ✅ Slack file attachment handling
- ✅ Multi-source content aggregation

## Testing Strategy

Use sample sales notes to verify:
1. ✅ Parsing handles messy input
2. ✅ MEDDPICC extraction is accurate
3. ✅ Coaching insights are actionable
4. ✅ Tone matches "Maverick" persona
5. ✅ Missing information is gracefully handled
6. ✅ URL detection and preparation for scraping
7. ✅ Document parsing utilities available

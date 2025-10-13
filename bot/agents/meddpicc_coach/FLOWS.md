# MEDDPICC Coach - Flow Architecture

This document describes the three distinct flows in the MEDDPICC Coach agent.

## Flow Overview

```
                    ┌─────────────────────────────────────┐
                    │         User Input (START)          │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │       Route Based on State:          │
                    │  1. followup_mode = True?            │
                    │  2. question_mode = True?            │
                    │  3. query empty?                     │
                    │  4. query has notes?                 │
                    └──────────┬───────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
    ┌────────┐          ┌──────────┐         ┌─────────────┐
    │ Flow 1 │          │  Flow 2  │         │   Flow 3    │
    │  Q&A   │          │ Analysis │         │  Follow-up  │
    └────────┘          └──────────┘         └─────────────┘
```

---

## Flow 1: Interactive Q&A Collection

**When:** User provides no notes (empty query) and not in question_mode yet

**Purpose:** Guide users through structured information gathering when they don't have notes

```
START
  │
  ├─► [qa_collector]
  │         │
  │         ├─ Ask Question 1/8 (Company)
  │         ├─ Store Answer → Ask Question 2/8 (Pain)
  │         ├─ Store Answer → Ask Question 3/8 (Metrics)
  │         ├─ Store Answer → Ask Question 4/8 (Economic Buyer)
  │         ├─ Store Answer → Ask Question 5/8 (Decision Criteria)
  │         ├─ Store Answer → Ask Question 6/8 (Decision Process)
  │         ├─ Store Answer → Ask Question 7/8 (Champion)
  │         ├─ Store Answer → Ask Question 8/8 (Competition)
  │         │
  │         └─► Compile all answers into notes
  │                    │
  │                    ▼
  └──────────► [parse_notes] → [Flow 2 continues...]
```

**State Management:**
- `question_mode: True` - Indicates we're in Q&A flow
- `current_question_index` - Tracks which question to ask next (1-8)
- `gathered_answers` - Dictionary storing responses by category

**User Experience:**
```
Bot: 🎯 MEDDPICC Analysis - Question 1/8
     Who's the company/contact? (Name, industry, size - say 'skip' if you don't know)

User: Acme Corp, B2B SaaS, 500 employees

Bot: 🎯 MEDDPICC Analysis - Question 2/8
     What problems are they trying to solve? (Business pain points - or 'skip')

User: Slow deployment times, taking 2+ weeks
...
```

---

## Flow 2: Direct Analysis

**When:** User provides notes directly (has query) and not in question_mode or followup_mode

**Purpose:** Analyze provided notes and generate MEDDPICC breakdown with coaching

```
START (with notes)
  │
  ▼
[parse_notes]
  │
  ├─ Clean and format notes
  ├─ Extract and scrape URLs (if present)
  ├─ Parse file attachments (PDF/DOCX)
  │
  ▼
[meddpicc_analysis]
  │
  ├─ Structure into MEDDPICC framework (GPT-4o)
  ├─ Identify what's present and missing
  ├─ Add source citations
  │
  ▼
[coaching_insights]
  │
  ├─ Generate Maverick's coaching advice (GPT-4o-mini)
  ├─ Suggest follow-up questions
  ├─ Store original_analysis for follow-ups
  ├─ Set followup_mode = True
  │
  ▼
END
  │
  └─► Final response with full MEDDPICC analysis
```

**State After Completion:**
- `meddpicc_breakdown` - Structured MEDDPICC analysis
- `coaching_insights` - Maverick's coaching advice
- `final_response` - Combined output
- `original_analysis` - Stored for follow-up context
- `followup_mode: True` - Enables follow-up questions

**Timing:**
- Parse Notes: ~2-3 seconds (+ URL scraping if applicable)
- MEDDPICC Analysis: ~2-3 seconds
- Coaching Insights: ~1-2 seconds
- **Total: ~6-8 seconds** (typical)

---

## Flow 3: Follow-up Questions (NEW!)

**When:** User sends new message after analysis is complete (followup_mode = True)

**Purpose:** Allow users to modify, clarify, or expand on the analysis

```
START (followup_mode = True)
  │
  ▼
[followup_handler]
  │
  ├─ Retrieve original_analysis from state
  ├─ Process user's follow-up question
  ├─ Generate context-aware response (GPT-4o)
  ├─ Keep followup_mode = True
  │
  ▼
END
  │
  └─► Response to follow-up question
       (User can ask more questions, loop continues)
```

**Supported Follow-up Types:**

### 1. Modifications
```
User: I don't use P in my process, drop it
Bot:  Got it! Let's adjust this for your process...
      [Regenerated MEDDIC analysis without Paper Process]
```

### 2. Clarifications
```
User: Tell me more about the Economic Buyer section
Bot:  Great question! In your Acme Corp deal, the Economic Buyer is...
      [Detailed explanation with context from their notes]
```

### 3. Additional Information
```
User: I forgot to mention they have a $500K budget
Bot:  Great, that's helpful! Let me update the Metrics section...
      [Updated analysis incorporating new budget info]
```

### 4. Conceptual Questions
```
User: What does Champion mean in MEDDPICC?
Bot:  A Champion is an internal advocate who...
      [Explanation with examples from their deal]
```

**State Management:**
- `followup_mode: True` - Stays true throughout follow-up conversation
- `original_analysis` - Contains full context from initial analysis
- `query` - The user's follow-up question

**Context Awareness:**
The followup_handler has access to:
- Complete MEDDPICC breakdown
- Coaching insights
- Original notes
- Any scraped content/sources

---

## Routing Logic

The graph uses priority-based routing at START:

```python
def route_start(state):
    # Priority 1: Follow-up mode (after analysis complete)
    if state.get("followup_mode"):
        return "followup_handler"

    # Priority 2: Q&A mode (interactive collection)
    if state.get("question_mode"):
        return "qa_collector"

    # Priority 3: No query (start Q&A)
    if not state.get("query"):
        return "qa_collector"

    # Priority 4: Has query (direct analysis)
    return "parse_notes"
```

## State Persistence

All flows use LangGraph checkpointing for conversation continuity:

- **Development:** MemorySaver (in-memory)
- **Production:** AsyncSqliteSaver (persistent SQLite DB)

This allows users to:
- Answer Q&A questions one at a time
- Return later to continue Q&A
- Ask multiple follow-up questions across sessions
- Maintain analysis context for days/weeks

## Complete Flow Example

```
User: @bot meddic
→ Flow 1: Q&A (8 questions)

User: Acme Corp
Bot:  Question 2/8...
→ Flow 1 continues

User: [completes Q&A]
→ Flow 2: Analysis runs
Bot:  [Full MEDDPICC analysis]

User: I don't use P, drop it
→ Flow 3: Follow-up
Bot:  [Modified MEDDIC analysis]

User: Tell me more about the Champion
→ Flow 3: Follow-up
Bot:  [Detailed Champion explanation]
```

## Node Functions

| Node | Flow | Purpose | LLM | Timing |
|------|------|---------|-----|--------|
| `qa_collector` | 1 | Ask questions, gather answers | None | Instant |
| `parse_notes` | 2 | Clean notes, scrape URLs | GPT-4o-mini | 2-3s |
| `meddpicc_analysis` | 2 | Structure MEDDPICC | GPT-4o | 2-3s |
| `coaching_insights` | 2 | Generate coaching | GPT-4o-mini | 1-2s |
| `followup_handler` | 3 | Answer follow-ups | GPT-4o | 1-2s |

## Benefits of Multi-Flow Architecture

1. **Flexibility:** Supports multiple user entry points
2. **Guidance:** Helps users who don't have structured notes
3. **Iteration:** Allows refinement after initial analysis
4. **Context:** Maintains conversation state across interactions
5. **User Control:** Users can customize output to their process

---

## Technical Implementation

### Key Files

- `state.py` - State definitions with followup_mode
- `graph_builder.py` - Flow routing and graph compilation
- `prompts.py` - Prompts for all three flows
- `nodes/qa_collector.py` - Flow 1 implementation
- `nodes/followup_handler.py` - Flow 3 implementation
- `nodes/parse_notes.py` - Flow 2 entry point
- `nodes/meddpicc_analysis.py` - Flow 2 analysis
- `nodes/coaching_insights.py` - Flow 2 coaching + follow-up setup

### State Schema

```python
MeddpiccAgentState:
    query: str                    # User input
    raw_notes: str               # Processed notes
    meddpicc_breakdown: str      # MEDDPICC analysis
    coaching_insights: str       # Coaching advice
    final_response: str          # Output

    # Flow 1 (Q&A)
    question_mode: bool          # In Q&A flow?
    current_question_index: int  # Which question (1-8)
    gathered_answers: dict       # Collected responses

    # Flow 3 (Follow-up)
    followup_mode: bool          # In follow-up flow?
    original_analysis: str       # Full context for follow-ups
```

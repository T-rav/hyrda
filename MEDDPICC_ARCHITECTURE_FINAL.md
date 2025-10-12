# MEDDPICC Coach - Final Architecture ✅

## Architecture Decisions

### 1. ✅ Entity Extraction for PDF Titles

**Added**: Smart entity extraction using GPT-4o-mini

**Before:**
```
MEDDPICC Sales Analysis.pdf
```

**After:**
```
Acme Corp - MEDDPICC Analysis.pdf
GlobalTech - MEDDPICC Analysis.pdf  
TechStartup - MEDDPICC Analysis.pdf
```

Extracts company/person name from notes for better file organization.

---

### 2. ✅ Document Extraction: Centralized in Main Handler

**Design Decision**: PDF/document extraction happens in **main bot handler**, NOT in individual agents.

#### Why This is Better

**❌ BAD (Agent-level extraction):**
```
Each agent implements its own:
- PDF parsing
- DOCX parsing
- File download
- Error handling
→ Code duplication
→ Inconsistent handling
→ More maintenance
```

**✅ GOOD (Centralized extraction):**
```
Main handler (message_handlers.py):
- Downloads files once
- Extracts text once
- Passes to all agents

Agents just receive clean text
→ No duplication
→ Consistent extraction
→ Single source of truth
```

#### How It Works

**Flow:**
```
1. User uploads PDF/DOCX to Slack
   ↓
2. Main handler (message_handlers.py)
   - process_file_attachments()
   - Downloads file
   - Extracts text (PDF, DOCX, PPTX, etc.)
   ↓
3. Passes document_content to agent
   ↓
4. Agent receives clean text in context
   - context["document_content"]
   - No file handling needed
```

**Code:**
```python
# bot/handlers/message_handlers.py
async def process_file_attachments(files, slack_service):
    """Central document extraction - used by ALL agents"""
    for file in files:
        if file.endswith('.pdf'):
            text = extract_pdf_text(content)
        elif file.endswith('.docx'):
            text = extract_office_text(content)
        # etc...
    return document_content

# Agent receives it
async def handle_bot_command(...):
    document_content = await process_file_attachments(files)
    context["document_content"] = document_content
    result = await agent.run(query, context)
```

---

### 3. ✅ MEDDPICC Coach Architecture

**What the agent handles:**

1. **URL Scraping** (agent-specific)
   - Detects URLs in input
   - Uses Tavily to scrape web content
   - Combines with text notes

2. **Document Content** (from handler)
   - Receives pre-extracted text from PDF/DOCX
   - Passed via `context["document_content"]`
   - No file download/parsing needed

3. **Combined Analysis**
   - Text notes
   - + Scraped URL content  
   - + Document attachment content
   - → Comprehensive MEDDPICC analysis

**Code:**
```python
# parse_notes.py
async def parse_notes(state, config):
    # Get document content from handler
    document_content = config["configurable"]["document_content"]

    # Agent-specific: URL scraping
    urls = extract_urls(query)
    scraped_content = await scrape_urls(urls)

    # Combine all sources
    all_content = raw_notes + scraped_content + document_content
    return {"raw_notes": all_content, ...}
```

---

## What This Means for Users

### Example 1: Text + URL
```
/meddic Call with Acme Corp. Check their site:
https://acmecorp.com/about

Budget approved for $150K.
```

**Processing:**
1. Text → extracted
2. URL → scraped by agent (Tavily)
3. Combined → MEDDPICC analysis

### Example 2: Text + PDF Attachment
```
[Upload: call-notes.pdf]
/meddic See attached notes from my call
```

**Processing:**
1. Text → extracted
2. PDF → extracted by handler (PyMuPDF)
3. Combined → MEDDPICC analysis

### Example 3: Text + URL + PDF
```
[Upload: acme-overview.pdf]
/meddic Call notes and their website:
https://acmecorp.com/about
```

**Processing:**
1. Text → extracted
2. PDF → extracted by handler
3. URL → scraped by agent
4. All combined → MEDDPICC analysis

---

## File Extraction Capabilities

### Centralized Handler Supports:
- ✅ PDF (PyMuPDF)
- ✅ DOCX (python-docx)
- ✅ XLSX (openpyxl)
- ✅ PPTX (python-pptx)
- ✅ TXT, MD, CSV
- ✅ Code files (.py, .js, etc.)
- ✅ Subtitle files (.vtt, .srt)

### Agent-Specific (MEDDPICC):
- ✅ URL scraping (Tavily)
- ✅ Web page extraction

---

## Benefits of This Design

1. **DRY (Don't Repeat Yourself)**
   - One document extraction implementation
   - All agents benefit from improvements

2. **Consistency**
   - Same PDF text for all agents
   - Predictable behavior

3. **Maintainability**
   - Fix bugs once, affects all agents
   - Add new file types once

4. **Performance**
   - File downloaded once
   - Extracted once
   - Cached for all agents

5. **Separation of Concerns**
   - Handler: Infrastructure (files, downloads)
   - Agent: Business logic (analysis)

---

## Code Organization

```
bot/handlers/message_handlers.py
├── process_file_attachments()      # Main entry point
├── extract_pdf_text()              # PDF extraction
├── extract_office_text()           # DOCX/XLSX/PPTX
└── extract_powerpoint_text()       # PPTX specific

bot/agents/meddic_agent.py
└── Receives document_content from context

bot/agents/meddpicc_coach/nodes/parse_notes.py
├── Gets document_content from config
├── Extracts URLs (agent-specific)
├── Scrapes URLs with Tavily
└── Combines all sources

bot/agents/meddpicc_coach/utils.py
└── [Can be removed - no longer needed]
```

---

## Implementation Status

- ✅ Entity extraction for PDF titles
- ✅ Centralized document extraction in handler
- ✅ Agent receives document_content from context
- ✅ URL scraping in agent (agent-specific)
- ✅ Combined content analysis
- ✅ No code duplication
- ✅ Clean architecture

---

## Future Enhancements

**Easy to add** (just modify handler):
- Google Docs API integration
- Notion page extraction
- Email parsing (.eml files)
- More office formats

**All agents automatically benefit!**

---

## Summary

✅ **Entity extraction**: Added to MEDDPICC agent  
✅ **Document extraction**: Centralized in main handler (correct design)  
✅ **URL scraping**: Agent-specific (unique to MEDDPICC)  
✅ **Clean architecture**: No duplication, easy maintenance  
✅ **Production ready**: All pieces working together

**Branch**: `meddic`
**Date**: October 11, 2025

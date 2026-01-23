# SEC Research - On-Demand Only

## Overview

SEC document research is now **on-demand only** - no scheduled jobs, no database persistence, no vector DB storage.

When the profile agent needs SEC data, it:
1. Fetches latest 10-K (annual report) + 4 most recent 8-Ks (material events) from SEC Edgar API
2. Chunks and vectorizes in-memory
3. Searches for relevant excerpts
4. Clears memory after use

## Why On-Demand?

**Before:**
- Scheduled job ingesting 10,000+ companies
- Database tables tracking documents
- Persistent vector storage
- Expensive and slow

**After:**
- Just-in-time fetching when needed
- In-memory processing
- No persistence overhead
- Fast and cost-effective

## Usage

### Basic Research

```python
from agents.company_profile.tools.sec_research import research_sec_filings

results = await research_sec_filings(
    company_identifier="AAPL",  # Ticker or CIK
    research_query="What are the company's main revenue sources?",
    openai_api_key=settings.openai_api_key,
    top_k=5  # Number of relevant excerpts
)

# Returns
{
    "success": True,
    "company_name": "Apple Inc.",
    "filings_searched": [
        {"type": "10-K", "date": "2024-09-28", "url": "..."},
        {"type": "8-K", "date": "2024-08-15", "url": "..."},
        ...
    ],
    "relevant_excerpts": [
        {
            "content": "iPhone sales represented 52% of total revenue...",
            "score": 0.89,
            "metadata": {"type": "10-K", "date": "2024-09-28"}
        },
        ...
    ]
}
```

### Formatted for LLM Context

```python
from agents.company_profile.tools.sec_research import format_sec_research_results

formatted = format_sec_research_results(results)
# Returns markdown-formatted string ready for LLM context
```

## Architecture

### Components

**1. SECOnDemandFetcher** (`services/sec_on_demand.py`)
- Fetches from SEC Edgar API
- Parses HTML to clean text
- No database dependencies

**2. SECInMemoryVectorSearch** (`services/sec_vector_search.py`)
- Generates OpenAI embeddings
- Stores vectors in numpy arrays
- Cosine similarity search
- Clears after use

**3. SEC Research Tool** (`tools/sec_research.py`)
- High-level interface
- Combines fetching + vectorization + search
- Returns formatted results

### What Documents Are Fetched?

For each company:
- **Latest 10-K**: Annual report with comprehensive business overview, financials, risk factors
- **4 Most Recent 8-Ks**: Material event disclosures (earnings, acquisitions, leadership changes, etc.)

### Why These Documents?

**10-K (Annual Report):**
- Business description and strategy
- Risk factors
- Financial statements
- Management discussion (MD&A)
- Most comprehensive document

**8-K (Current Reports):**
- Real-time material events
- Earnings releases
- Acquisitions and divestitures
- Leadership changes
- More recent than 10-K

## SEC Edgar API

Uses the official SEC Edgar API (no authentication required):
- **Company Info**: `https://data.sec.gov/submissions/CIK{cik}.json`
- **Filings**: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{file}`
- **Ticker Lookup**: `https://www.sec.gov/files/company_tickers.json`

**Rate Limiting:** 10 requests/second (enforced by 0.1s delay)

**User-Agent Required:** `"8th Light InsightMesh insightmesh@8thlight.com"`

## Example: Profile Agent Integration

```python
# In profile agent's deep research node
async def research_financials(state: ProfileAgentState):
    query = state["query"]
    company = extract_company_name(query)

    # Fetch and search SEC filings
    sec_results = await research_sec_filings(
        company_identifier=company,
        research_query="What are the company's revenue streams, margins, and growth rates?",
        openai_api_key=settings.openai_api_key,
        top_k=5
    )

    # Add to context
    if sec_results["success"]:
        formatted = format_sec_research_results(sec_results)
        state["research_data"]["sec_filings"] = formatted

    return state
```

## Cost & Performance

**Typical Request (e.g., Apple):**
- Fetch 1 10-K (~500KB) + 4 8-Ks (~50KB each)
- Total: ~700KB of text
- Chunks: ~350 chunks (2000 chars each)
- Embeddings: ~350 embeddings (~$0.01)
- Search: In-memory, instant
- **Total time: ~10-15 seconds**
- **Total cost: ~$0.01 per research query**

**vs. Pre-Indexed Approach:**
- Index 10,000+ companies: ~$100-200
- Storage: Persistent database + vector DB
- Updates: Scheduled jobs
- **Much more expensive, slower to update**

## Removed Components

The following were removed as part of the on-demand migration:

### Scheduled Jobs (tasks/jobs/)
- ❌ `sec_ingestion_job.py` - Batch ingestion for all companies
- ❌ `sec_cleanup_job.py` - Cleanup old documents
- ❌ `run_sec_ingestion.py` - CLI runner

### Services (tasks/services/)
- ❌ `sec_ingestion_orchestrator.py` - Batch processing orchestration
- ❌ `sec_document_tracking_service.py` - Database tracking
- ❌ `sec_symbol_service.py` - Company symbol management
- ❌ `sec_document_builder.py` - Document building
- ❌ `sec_section_filter.py` - Section filtering
- ❌ `sec_edgar_client.py` - (Replaced by on-demand fetcher)

### Database Tables
- ❌ `sec_documents_data` - Tracked ingested documents
- ❌ `sec_symbol_data` - Company ticker/CIK mapping

### Migrations
- Migration `017_drop_sec_tables.py` drops all SEC tables

## Migration Instructions

To apply the database changes:

```bash
# Apply migration (drops SEC tables)
cd tasks
alembic upgrade head

# To rollback (not recommended - recreates tables but no data)
alembic downgrade -1
```

## Future Enhancements

Possible improvements:
- **Smarter document selection**: Fetch specific 8-Ks based on query (e.g., earnings reports only)
- **Section extraction**: Parse specific sections (Business, Risk Factors, MD&A)
- **Caching**: Short-term cache (1 hour) to avoid re-fetching same company
- **Parallel fetching**: Download multiple filings simultaneously
- **Query-focused chunking**: Chunk based on relevance to query

## Troubleshooting

**SEC API Rate Limiting:**
- The client enforces 0.1s delay between requests (10 req/s max)
- If you get 403 errors, ensure User-Agent header is set correctly

**Missing Filings:**
- Some companies may not have recent 8-Ks
- 10-K is annual, so may be up to 1 year old
- Check company's SEC filing page: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}`

**Large Documents:**
- 10-Ks can be 500KB+ of text
- Chunking creates 200-400 chunks
- Embedding generation may take 10-20 seconds
- This is normal and expected

**Out of Memory:**
- Each research query holds ~350 embeddings in RAM
- Vectors are cleared after search
- If multiple concurrent queries, consider rate limiting

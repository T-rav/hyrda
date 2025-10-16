# SEC Filing Ingestion

Ingest SEC filings (10-K, 10-Q, 8-K) into your vector database for sales intelligence and company research.

## Overview

The SEC Edgar ingestion system downloads and processes SEC filings from public companies, extracting key business intelligence including:

- **10-K Annual Reports**: Risk factors, strategic priorities, R&D investments, financial performance
- **10-Q Quarterly Reports**: Quarterly updates, operational changes, emerging risks
- **8-K Current Reports**: Material events, acquisitions, executive changes, product announcements

All filings are:
- ✅ **Idempotent**: Content hashing prevents duplicate ingestion
- ✅ **Tracked**: MySQL database tracks all ingested documents
- ✅ **Versioned**: Re-ingestion when content changes
- ✅ **Searchable**: Embedded in vector database for semantic search

## Setup

### 1. Install Dependencies

```bash
cd ingest
pip install -e .
```

This installs:
- `httpx` for SEC API calls
- `beautifulsoup4` for HTML parsing
- All existing vector/embedding dependencies

### 2. Run Database Migration

```bash
cd ../tasks
alembic -c alembic_data.ini upgrade head
```

This creates the `sec_documents_data` table for tracking ingested filings.

### 3. Configure Environment

Ensure your `.env` has vector database settings (same as Google Drive ingestion):

```bash
# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=knowledge_base

# Embeddings
OPENAI_API_KEY=your_key_here
EMBEDDING_MODEL=text-embedding-3-large
```

## Usage

### Basic Usage

Ingest most recent 10-K for a company:

```bash
# By CIK (Central Index Key)
python ingest_sec.py --cik 0000320193

# By ticker symbol
python ingest_sec.py --ticker AAPL
```

### Advanced Usage

```bash
# Ingest multiple recent filings (e.g., last 3 years of 10-Ks)
python ingest_sec.py --cik 0000320193 --limit 3

# Ingest 10-Q quarterly reports instead
python ingest_sec.py --cik 0000320193 --filing-type 10-Q --limit 4

# Ingest 8-K current reports
python ingest_sec.py --cik 0000320193 --filing-type 8-K --limit 10

# Specify custom vector database
python ingest_sec.py --cik 0000320193 \
  --qdrant-host qdrant.example.com \
  --qdrant-port 6333 \
  --collection knowledge_base

# Custom embedding model
python ingest_sec.py --cik 0000320193 \
  --embedding-model text-embedding-3-small
```

### Batch Ingestion

Create a `companies.txt` file with CIKs or ticker symbols:

```text
# companies.txt - Public tech companies
0000320193  # Apple
0000789019  # Microsoft
GOOGL       # Alphabet
AMZN        # Amazon
META        # Meta
TSLA        # Tesla
NVDA        # NVIDIA
NFLX        # Netflix
CRM         # Salesforce
```

Then run:

```bash
python ingest_sec.py --companies-file companies.txt --filing-type 10-K --limit 3
```

## Finding CIKs

### Method 1: SEC Company Search
1. Go to https://www.sec.gov/edgar/searchedgar/companysearch
2. Search for company name
3. CIK is shown in search results

### Method 2: From SEC URL
When viewing a company on SEC.gov, the CIK is in the URL:
```
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193
                                                                ^^^^^^^^^^
                                                                CIK here
```

### Method 3: Known Tickers
The CLI includes built-in lookup for major tech companies:
- AAPL, MSFT, GOOGL, AMZN, META, TSLA, NVDA, NFLX, CRM, ORCL

To add more, edit `sec_edgar_client.py` → `lookup_cik()` method.

## What Gets Ingested

Each SEC filing is processed as follows:

### 1. **Download**
- Fetches HTML filing from SEC Edgar
- Parses and cleans HTML to plain text
- Removes scripts, styles, headers

### 2. **Tracking**
- Computes SHA-256 content hash
- Checks if already ingested (idempotent)
- Skips if content unchanged
- Re-indexes if content changed

### 3. **Chunking**
- Splits text into semantic chunks
- Injects document metadata into each chunk:
  ```
  [Apple Inc - 10-K - 2024-11-01]

  <chunk content>
  ```

### 4. **Vector Storage**
- Generates embeddings using OpenAI
- Stores in Qdrant with rich metadata:
  ```json
  {
    "source": "sec_edgar",
    "cik": "0000320193",
    "company_name": "Apple Inc",
    "filing_type": "10-K",
    "filing_date": "2024-11-01",
    "accession_number": "0000320193-24-000123",
    "document_url": "https://sec.gov/...",
    "chunk_index": 0,
    "total_chunks": 45
  }
  ```

### 5. **Database Tracking**
- Records in `sec_documents_data` table:
  - Accession number (unique ID)
  - Content hash (for deduplication)
  - Vector UUID (for chunk IDs)
  - Chunk count
  - Ingestion status and timestamps

## Metadata Stored

Each chunk includes:

| Field | Description | Example |
|-------|-------------|---------|
| `source` | Always "sec_edgar" | `sec_edgar` |
| `cik` | Central Index Key | `0000320193` |
| `company_name` | Company name | `Apple Inc` |
| `filing_type` | Type of filing | `10-K`, `10-Q`, `8-K` |
| `filing_date` | Date filed with SEC | `2024-11-01` |
| `accession_number` | Unique SEC document ID | `0000320193-24-000123` |
| `document_url` | Direct link to filing | `https://sec.gov/...` |
| `chunk_id` | Chunk identifier | `0000320193-24-000123_chunk_0` |
| `chunk_index` | Chunk position | `0`, `1`, `2`, ... |
| `total_chunks` | Total chunks in document | `45` |

## Integration with Company Profile Agent

The company profile agent automatically searches SEC filings when researching public companies:

```python
# Internal search finds SEC filings by company name
results = await internal_search_tool.run(
    "Apple strategic priorities and risks"
)

# Returns chunks from 10-K with:
# - Risk Factors section → consulting opportunities
# - MD&A section → strategic initiatives
# - R&D investments → technology priorities
```

## Examples

### Example 1: Ingest Apple's Recent 10-Ks

```bash
python ingest_sec.py --ticker AAPL --limit 3
```

Output:
```
Processing Apple Inc (CIK: 0000320193)
Fetching 10-K (index 0) for CIK 0000320193...
Processing: Apple Inc - 10-K filed on 2024-11-01
Chunking content (487,234 chars)...
Created 98 chunks
Generating embeddings for 98 chunks...
Upserting 98 chunks to vector store...
✅ Successfully ingested: Apple Inc - 10-K (98 chunks)
```

### Example 2: Quarterly Reports for Multiple Companies

```bash
# Create file
echo "AAPL\nMSFT\nGOOGL" > tech_companies.txt

# Ingest
python ingest_sec.py --companies-file tech_companies.txt --filing-type 10-Q --limit 4
```

### Example 3: Check What's Already Ingested

```python
from ingest.services import SECDocumentTrackingService

tracker = SECDocumentTrackingService()

# Get all filings for Apple
filings = tracker.get_company_filings(cik="0000320193")

for filing in filings:
    print(f"{filing['filing_date']}: {filing['filing_type']} - {filing['ingestion_status']}")
```

## Rate Limiting

The SEC requests a maximum of **10 requests per second**. The client includes automatic rate limiting (100ms delay between requests).

## Common Issues

### Issue: "No 10-K filing found"
- **Cause**: Company may not have filed yet, or may not be public
- **Solution**: Check SEC.gov to verify filings exist

### Issue: "Could not find CIK for ticker"
- **Cause**: Ticker not in built-in lookup
- **Solution**: Look up CIK manually and use `--cik` instead

### Issue: "Connection timeout"
- **Cause**: SEC servers may be slow or rate limited
- **Solution**: Retry or increase timeout in `sec_edgar_client.py`

## Architecture

```
ingest_sec.py (CLI)
    ↓
SECIngestionOrchestrator
    ↓
    ├─→ SECEdgarClient (download filings)
    ├─→ EmbeddingProvider (chunk + embed)
    ├─→ QdrantVectorStore (store embeddings)
    └─→ SECDocumentTrackingService (track in MySQL)
```

## Future Enhancements

Potential additions:
- [ ] Automatic section extraction (Risk Factors, MD&A, Business Overview)
- [ ] Earnings call transcript ingestion
- [ ] Proxy statement (DEF 14A) ingestion
- [ ] Patent filing cross-reference
- [ ] Automatic ticker → CIK lookup via SEC API
- [ ] Scheduled ingestion (daily/weekly cron jobs)
- [ ] Delta ingestion (only new filings since last run)

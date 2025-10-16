# SEC Filing Retention Policy

## Overview

This document defines the retention policy for SEC filings in the InsightMesh knowledge base.

## Two-Tier Storage

### 1. MySQL Tracking Database
**Retention: Forever** ✅

Stores:
- Filing metadata (CIK, accession number, filing date, company name)
- Content hash (for deduplication)
- Ingestion status and timestamps
- Vector UUID references

Why keep forever:
- Cheap storage (~1KB per filing)
- Audit trail for compliance
- Historical ingestion patterns
- Enables idempotent re-ingestion
- Can regenerate embeddings if needed

### 2. Qdrant Vector Database
**Retention: Based on Filing Type**

Stores:
- Embedded chunks of filing content
- Rich metadata for retrieval
- Expensive storage (~1-2MB per filing)

## Retention Periods

### Annual Reports (10-K)
**Keep: 3 most recent per company**

Rationale:
- Shows current year + 2 years of historical comparison
- Captures strategic direction trends
- Balances recency with historical context
- ~3 years is optimal for sales intelligence

Example for Apple (CIK 0000320193):
```
Keep:
✅ 2024 10-K (current strategy, recent risks)
✅ 2023 10-K (prior year comparison)
✅ 2022 10-K (3-year trend analysis)

Delete:
❌ 2021 10-K (outdated priorities, old leadership)
❌ 2020 10-K (pre-pandemic context, less relevant)
```

### Quarterly Reports (10-Q)
**Keep: 8 most recent per company (2 years)**

Rationale:
- Shows 2 years of quarterly progression
- Captures seasonal patterns
- Recent operational changes
- More frequent updates = shorter retention needed

Example:
```
Keep:
✅ Q4 2024, Q3 2024, Q2 2024, Q1 2024
✅ Q4 2023, Q3 2023, Q2 2023, Q1 2023

Delete:
❌ Anything older than 2 years
```

### Current Events (8-K)
**Keep: Last 12 months**

Rationale:
- Breaking news, acquisitions, executive changes
- High volume, time-sensitive
- Most relevant within 12 months
- 10-K/10-Q capture important events in context

Example:
```
Keep:
✅ Any 8-K filed after Jan 16, 2024

Delete:
❌ Any 8-K filed before Jan 16, 2024
```

## Storage Estimates

### Per Company (3 years of 10-Ks)
```
Typical 10-K filing:
- Raw text: 500KB
- Chunks: ~100 (1500 chars each with overlap)
- Embeddings: 100 × 3072 floats × 4 bytes = 1.2MB
- Metadata: ~50KB

Total per 10-K: ~1.3MB
Total for 3 years: ~4MB per company
```

### Portfolio of 100 Companies
```
100 companies × 4MB = 400MB (10-K only)

With 10-Q (8 quarters × 100 companies):
+ 800MB

With 8-K (assume 5/year × 100 companies):
+ 50MB

Total: ~1.25GB for comprehensive coverage
```

## Cleanup Schedule

### Automated Cleanup Job
**Run: Monthly** (first Sunday of each month)

```bash
# Cron schedule: 0 2 * * 0 (2 AM on first Sunday)
cd /app/tasks && python jobs/sec_cleanup.py
```

### Manual Cleanup
```bash
# Dry run (see what would be deleted)
python tasks/jobs/sec_cleanup.py --dry-run

# Actually delete
python tasks/jobs/sec_cleanup.py

# Custom retention
python tasks/jobs/sec_cleanup.py --keep-10k 5 --keep-10q 12
```

## Configuration Options

### Conservative (More History)
```bash
# Keep 5 years of 10-K, 3 years of 10-Q
python sec_cleanup.py --keep-10k 5 --keep-10q 12 --keep-8k-months 24
```

**Use when:**
- Analyzing long-term trends
- Researching established companies (30+ years)
- Academic or compliance research

### Aggressive (Less History)
```bash
# Keep 2 years of 10-K, 1 year of 10-Q
python sec_cleanup.py --keep-10k 2 --keep-10q 4 --keep-8k-months 6
```

**Use when:**
- Storage constrained
- Fast-moving industries (tech startups)
- Only care about very recent intelligence

### Recommended (Default)
```bash
# Keep 3 years of 10-K, 2 years of 10-Q
python sec_cleanup.py --keep-10k 3 --keep-10q 8 --keep-8k-months 12
```

**Best for:**
- B2B sales intelligence
- Consulting opportunity identification
- Strategic research

## Re-ingestion Strategy

Since MySQL tracking keeps all historical records:

### Scenario: Need Older Data
```bash
# Re-ingest 5 years of Apple 10-Ks
python tasks/jobs/run_sec_ingestion.py --ticker AAPL --filing-type 10-K --limit 5
```

The system will:
1. Check content hash in MySQL
2. Skip if already in vector DB
3. Re-embed only if missing or content changed

### Scenario: Storage Upgrade
```bash
# First, adjust retention policy
# Then re-ingest for all companies
while read cik; do
  python run_sec_ingestion.py --cik $cik --filing-type 10-K --limit 5
done < target_companies.txt
```

## Monitoring

### Check Current Status
```sql
-- Count filings by type and age
SELECT
  filing_type,
  YEAR(STR_TO_DATE(filing_date, '%Y-%m-%d')) as filing_year,
  COUNT(*) as count,
  SUM(chunk_count) as total_chunks
FROM sec_documents_data
WHERE ingestion_status = 'success'
GROUP BY filing_type, filing_year
ORDER BY filing_type, filing_year DESC;
```

### Estimated Vector DB Size
```sql
-- Estimate total embeddings stored
SELECT
  COUNT(*) as total_filings,
  SUM(chunk_count) as total_chunks,
  ROUND(SUM(chunk_count) * 12 / 1024, 2) as estimated_mb
FROM sec_documents_data
WHERE ingestion_status = 'success';

-- Assumptions:
-- Each chunk = 3072 floats × 4 bytes = 12KB
```

## Business Value by Retention Period

### 1 Year: ⭐⭐
- Very recent data only
- Misses important trends
- Not enough historical context

### 2 Years: ⭐⭐⭐⭐
- Good for fast-moving industries
- Shows year-over-year comparison
- Captures most relevant intelligence

### 3 Years: ⭐⭐⭐⭐⭐ (Recommended)
- Optimal balance
- Trend analysis possible
- Strategic direction clear
- Not bloated with outdated info

### 5 Years: ⭐⭐⭐
- Long-term trends
- May include outdated priorities
- Higher storage costs
- Diminishing returns

## Recommendations by Use Case

### B2B Sales Intelligence (8th Light)
**Recommended: 3 years of 10-K, 2 years of 10-Q**
- Focus on current strategic initiatives
- Recent tech stack and investments
- Current leadership priorities
- Consulting opportunity signals

### Investment Research
**Recommended: 5 years of 10-K, 3 years of 10-Q**
- Long-term financial trends
- Multi-year strategic execution
- Regulatory compliance history

### Competitive Intelligence
**Recommended: 2 years of 10-K, 1 year of 10-Q**
- Fast-moving market dynamics
- Recent product launches
- Current competitive positioning

### Compliance/Legal
**Recommended: Keep all in MySQL, selective in vector DB**
- Full audit trail in MySQL
- Vector DB for semantic search of recent filings
- Can re-ingest older filings as needed

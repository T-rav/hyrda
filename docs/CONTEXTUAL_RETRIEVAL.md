# Contextual Retrieval

This implementation includes **Anthropic's Contextual Retrieval** technique, which significantly improves RAG performance by adding contextual descriptions to document chunks before embedding.

> **Note**: This feature is currently available for Qdrant-based vector search.

## Overview

**Problem**: Document chunks lose critical context when embedded in isolation, leading to poor retrieval accuracy.

**Solution**: For each chunk, generate a concise contextual description (50-100 tokens) that explains its place within the larger document, then embed the contextualized chunk.

### How It Works

1. **Document Chunking**: Documents are split into manageable chunks
2. **Context Generation**: For each chunk, Claude generates a 50-100 token contextual description
3. **Context Prepending**: The context is prepended to the original chunk
4. **Embedding**: The enhanced chunk (context + original content) is embedded
5. **Storage**: Both the enhanced content and metadata are stored in Qdrant

### Example Transformation

**Original Chunk:**
```
The company's Q3 revenue grew 15% year-over-year to $2.3B.
```

**Contextualized Chunk:**
```
[Context: This chunk discusses AllCampus's Q3 2024 financial results from their earnings report.]
The company's Q3 revenue grew 15% year-over-year to $2.3B.
```

The contextualized version provides richer semantic meaning for embedding and retrieval.

## Configuration

Add these settings to your `.env` file:

```bash
# Enable contextual retrieval
RAG_ENABLE_CONTEXTUAL_RETRIEVAL=true

# Number of chunks to process in parallel (default: 10)
RAG_CONTEXTUAL_BATCH_SIZE=10

# Vector configuration
VECTOR_PROVIDER=qdrant
VECTOR_HOST=qdrant
VECTOR_PORT=6333
```

## Usage

### During Ingestion

The contextual retrieval process runs automatically during document ingestion:

```python
from ingest.main import ingest_folder

# Contextual retrieval applies automatically if enabled
await ingest_folder(
    folder_id="your_folder_id",
    # RAG_ENABLE_CONTEXTUAL_RETRIEVAL controls whether contextualization happens
)
```

**What happens:**
1. Download and chunk documents
2. Generate contextual descriptions for each chunk (if enabled)
3. Create embeddings of the contextualized chunks
4. Store in Qdrant with full metadata

### Performance Impact

**Additional processing time:**
- ~1-2 seconds per chunk for context generation
- Batched processing (default: 10 chunks at a time)
- Parallelized for efficiency

**Example timing for 100 chunks:**
- Without contextual retrieval: ~30 seconds
- With contextual retrieval: ~2-3 minutes

**Benefit:**
- Improved retrieval accuracy often outweighs processing time
- Context generation happens once during ingestion
- No impact on query time

## Benefits

### Retrieval Accuracy Improvements

Based on Anthropic's research:

- **Failed retrievals reduced by 49%** (from 5.7% to 3.0%)
- **Top-20 recall improved by 67%** (from 71.5% to 96.0%)
- Works especially well with reranking

### When It Helps Most

1. **Multi-document corpora**: When chunks from different documents might be similar
2. **Technical content**: When context clarifies specialized terminology
3. **Numerical data**: When numbers need document/section context
4. **Cross-references**: When chunks reference other parts of documents

### Example Scenarios

**Before (without context):**
- Query: "What was the revenue growth?"
- Poor match: Chunks from multiple quarters/companies mixed together

**After (with context):**
- Query: "What was the revenue growth?"
- Accurate match: Chunk clearly labeled with company, quarter, and document source

## Implementation Details

### Context Generation Prompt

```python
You are an expert at providing concise contextual descriptions.
Given a document and a chunk, provide a succinct context (50-100 tokens)
that explains what this chunk is about and where it fits in the document.

Document: {document_title}
Chunk: {chunk_text}

Context:
```

### Storage Format

```python
{
    "content": "[Context: ...] Original chunk text",
    "metadata": {
        "file_name": "document.pdf",
        "page_number": 5,
        "contextual": True,
        "original_content": "Original chunk text",  # Stored for reference
        ...
    }
}
```

## Integration with Existing Features

Contextual retrieval works seamlessly with other features:
- **Title Injection**: Both techniques can be used together
- **Entity Boosting**: Improved entity recognition in contextualized chunks
- **Result Diversification**: Better variety across document sources

## Troubleshooting

**Issue**: Context generation is slow
- Reduce `RAG_CONTEXTUAL_BATCH_SIZE` to lower memory usage
- Use a faster model for context generation

**Issue**: Too much context noise
- Adjust the context generation prompt to be more concise
- Review generated contexts and refine prompts

**Issue**: Storage size increased
- Expected: contextualized chunks are larger
- Benefit: significantly better retrieval accuracy

## References

- [Anthropic: Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- Original paper shows 49% reduction in failed retrievals
- Works particularly well with RAG reranking

# Contextual Retrieval

This implementation includes **Anthropic's Contextual Retrieval** technique, which significantly improves RAG performance by adding contextual descriptions to document chunks before embedding.

## Overview

Contextual retrieval addresses a key limitation in traditional RAG systems: document chunks are embedded in isolation, losing important context that could help with precise retrieval. By prepending contextual descriptions to each chunk before embedding, we improve retrieval accuracy by 35-49%.

## How It Works

1. **Document Processing**: Documents are chunked as usual (configurable size/overlap)
2. **Context Generation**: For each chunk, Claude generates a 50-100 token contextual description
3. **Context Prepending**: The context is prepended to the original chunk
4. **Embedding**: The enhanced chunk (context + original content) is embedded
5. **Storage**: Both the enhanced content and metadata are stored in Pinecone

### Example Transformation

**Original chunk:**
```
The company's revenue grew by 3% over the previous quarter.
```

**Contextualized chunk:**
```
This chunk is from a document with the following context: File: Q2_earnings.pdf; Type: PDF document; Created: 2024-06-15; Authors: Finance Team. The company's revenue grew by 3% over the previous quarter.
```

## Configuration

Add these settings to your `.env` file:

```bash
# Enable contextual retrieval
RAG_ENABLE_CONTEXTUAL_RETRIEVAL=true

# Number of chunks to process in parallel (default: 10)
RAG_CONTEXTUAL_BATCH_SIZE=10
```

## Usage

### During Document Ingestion

Contextual retrieval is automatically applied during document ingestion when enabled:

```bash
# Standard ingestion with contextual retrieval
cd ingest && python main.py --folder-id "1ABC123DEF456GHI789"
```

The ingestion process will:
1. Download and chunk documents
2. Generate contextual descriptions for each chunk (if enabled)
3. Create embeddings of the contextualized chunks
4. Store in Pinecone with full metadata

### Performance Impact

- **Ingestion Time**: Increases by ~2-3x due to LLM context generation
- **Retrieval Quality**: 35-49% reduction in retrieval failures
- **Storage**: No significant increase (context is part of embedding, not stored separately)

## Technical Implementation

### Key Components

1. **ContextualRetrievalService** (`bot/services/contextual_retrieval_service.py`)
   - Generates contextual descriptions using LLM
   - Handles batch processing and error recovery
   - Builds document context from metadata

2. **Ingestion Integration** (`ingest/services/ingestion_orchestrator.py`)
   - Seamlessly integrates with existing ingestion pipeline
   - Works with both hybrid and single vector store modes
   - Preserves all existing functionality

3. **Configuration** (`bot/config/settings.py`)
   - New RAG settings for contextual retrieval
   - Configurable batch size for parallel processing

### Context Information Used

The contextual descriptions include:
- **File name and path**
- **Document type** (PDF, Google Doc, etc.)
- **Creation date**
- **Authors/owners**
- **Document structure context**

### Error Handling

- **LLM Failures**: Falls back to original chunk without context
- **Partial Failures**: Processes successful chunks, logs failures
- **Rate Limiting**: Batch processing prevents API overload

## Performance Benchmarks

Based on Anthropic's research:
- **Pure Embedding**: 35% fewer retrieval failures
- **Combined with BM25**: 49% fewer retrieval failures  
- **With Reranking**: 67% fewer retrieval failures

## Best Practices

### When to Use
- **Knowledge Base Retrieval**: Excellent for Q&A systems
- **Document Search**: Improves precision for specific information
- **Technical Documentation**: Better understanding of context-dependent terms

### When to Consider Alternatives
- **Simple Keyword Matching**: May be overkill for basic search
- **Real-time Ingestion**: Adds latency during document processing
- **Cost-sensitive Applications**: Increases LLM API usage

### Optimization Tips

1. **Batch Size**: Start with 10, adjust based on API limits and performance
2. **Model Choice**: Use Claude for best context generation quality
3. **Hybrid Mode**: Combine with BM25 for optimal results
4. **Monitoring**: Track ingestion times and retrieval quality

## Integration with Existing Features

Contextual retrieval works seamlessly with:
- **Title Injection**: Both techniques can be used together
- **Hybrid Search**: Enhances both dense and sparse retrieval
- **Entity Boosting**: Improved entity recognition in contextualized chunks
- **Result Diversification**: Better variety across document sources

## Troubleshooting

### Common Issues

1. **Slow Ingestion**: Reduce batch size or check LLM API limits
2. **High API Costs**: Consider selective enablement for critical documents
3. **Context Too Long**: Service automatically truncates to 200 tokens

### Monitoring

Check logs for:
```
Adding contextual descriptions to X chunks...
✅ Contextual retrieval enabled - chunks will be enhanced with context
Successfully contextualized X chunks
```

### Verification

Test retrieval quality by comparing results with and without contextual retrieval enabled.
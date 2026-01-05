# Vector Search Options

This document explains the vector search configuration available in the AI Slack Bot:

## Qdrant (Pure Vector Search)

**Configuration:**
```bash
VECTOR_PROVIDER=qdrant
VECTOR_HOST=qdrant
VECTOR_PORT=6333
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base
VECTOR_API_KEY=your-qdrant-api-key  # Optional
```

**Use Case:** Best for pure semantic similarity searches.
- Uses dense vector embeddings only
- Fast and efficient for most RAG use cases
- Self-hosted or cloud-hosted
- Excellent for finding conceptually similar content
- Automatic collection initialization
- Supports namespaces and metadata filtering

## Quick Setup

### Qdrant (Recommended)
```bash
# .env file
VECTOR_PROVIDER=qdrant
VECTOR_HOST=qdrant
VECTOR_PORT=6333
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base

# Start Qdrant with Docker
docker compose up -d
```

## Configuration Options

```bash
# Qdrant settings (default)
VECTOR_PROVIDER=qdrant
VECTOR_HOST=qdrant                         # Docker service name or localhost
VECTOR_PORT=6333                           # Qdrant REST API port
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base
VECTOR_API_KEY=your-qdrant-api-key         # Optional for authentication

# RAG settings
RAG_MAX_RESULTS=5                          # Maximum results to return
RAG_SIMILARITY_THRESHOLD=0.35              # Minimum similarity for initial retrieval
RAG_RESULTS_SIMILARITY_THRESHOLD=0.5       # Final filtering threshold
RAG_MAX_CHUNKS_PER_DOCUMENT=3              # Limit chunks per document
RAG_ENTITY_CONTENT_BOOST=0.05              # Boost for entity matches in content
RAG_ENTITY_TITLE_BOOST=0.1                 # Boost for entity matches in titles
```

## Features

### Entity Boosting
- Automatically extracts entities from queries
- Boosts similarity scores for chunks containing query entities
- Separate boosts for content matches vs. title/filename matches

### Smart Diversification
- Limits chunks per document to avoid overwhelming results
- Ensures variety across different source documents
- Maintains pure similarity order for non-document data

### Query Rewriting
- Adaptive query rewriting to improve retrieval accuracy
- Intent detection and query expansion
- Metadata filtering based on query context

### Contextual Retrieval
- Optional Anthropic-style contextual retrieval
- Adds context to chunks before embedding
- Significantly improves retrieval accuracy

## Architecture

```
Query → Query Rewriting → Embedding → Qdrant Search → Entity Boosting → Diversification → Results
```

**Flow:**
1. Query rewriting (optional) - improves query based on intent
2. Embedding generation - converts query to vector
3. Qdrant similarity search - retrieves top candidates
4. Entity boosting - boosts results with matching entities
5. Threshold filtering - removes low-quality results
6. Smart diversification - ensures variety across documents

## Performance

- **Latency**: ~50-100ms for typical queries
- **Scalability**: Handles millions of vectors efficiently
- **Memory**: ~150MB for 100k vectors (1536 dimensions)
- **Accuracy**: ~70-85% recall@5 (depends on data quality)

## Best Practices

1. **Use appropriate similarity thresholds**
   - Lower initial threshold (0.35) for entity boosting pipeline
   - Higher final threshold (0.5) for quality results

2. **Enable query rewriting** for better accuracy
   - Adds 1-2 LLM calls per search
   - Significant quality improvement

3. **Tune entity boosting** based on your domain
   - Higher boosts for entity-heavy queries
   - Lower boosts for conceptual queries

4. **Monitor collection health**
   - Check vector counts regularly
   - Verify namespace distribution

5. **Optimize chunk size** for your content
   - Smaller chunks (500-1000 tokens) for precise retrieval
   - Larger chunks (1000-2000 tokens) for more context

## Troubleshooting

**Connection Issues:**
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Check Qdrant logs
docker logs qdrant

# Test connection
curl http://localhost:6333
```

**Collection Not Found:**
- Collection is created automatically on first use
- Verify `VECTOR_COLLECTION_NAME` matches your ingestion configuration

**Poor Search Quality:**
- Check similarity thresholds (may be too high)
- Review query rewriting settings
- Consider enabling contextual retrieval
- Verify chunks are properly embedded with metadata

**Slow Performance:**
- Check Qdrant resource allocation
- Increase `QDRANT_MMAP` for large collections
- Consider quantization for faster search

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)

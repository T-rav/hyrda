# Vector Search Options

This document explains the three different search configurations available in the AI Slack Bot:

## 1. Pinecone (Pure Vector Search)
**Configuration:**
```bash
VECTOR_PROVIDER=pinecone
VECTOR_API_KEY=your-pinecone-key
VECTOR_COLLECTION_NAME=knowledge_base
RAG_ENABLE_HYBRID_SEARCH=false
```

**Use Case:** Best for pure semantic similarity searches.
- Uses dense vector embeddings only
- Fast and efficient for most RAG use cases
- Requires Pinecone API key
- Excellent for finding conceptually similar content

## 2. Elasticsearch (Traditional BM25 + Vector Boost)
**Configuration:**
```bash
VECTOR_PROVIDER=elasticsearch  
VECTOR_URL=http://localhost:9200
VECTOR_COLLECTION_NAME=knowledge_base
RAG_ENABLE_HYBRID_SEARCH=false
```

**Use Case:** Traditional Elasticsearch with vector similarity boost.
- **Primary:** BM25 keyword-based search (traditional Elasticsearch)
- **Secondary:** Vector similarity boost (0.5x multiplier)
- Combines exact keyword matching with semantic understanding
- Self-hosted with no external dependencies
- Best of both worlds: traditional search enhanced by AI

## 3. Hybrid Search (Dual Pipeline with RRF)
**Configuration:**
```bash
VECTOR_PROVIDER=elasticsearch  # Must use Elasticsearch for hybrid
VECTOR_URL=http://localhost:9200
RAG_ENABLE_HYBRID_SEARCH=true
HYBRID_ENABLED=true
HYBRID_RERANKER_ENABLED=true
```

**Use Case:** Highest search quality with separate dense+sparse pipelines.
- **Separate pipelines:** Dense vector search AND BM25 sparse search
- **Fusion:** Reciprocal rank fusion (RRF) to combine results
- **Reranking:** Optional cross-encoder reranking for precision
- Most comprehensive but also most complex
- Best for enterprise-grade search quality

## Quick Setup Examples

### Traditional Elasticsearch (BM25 + Vector Boost)
```bash
# .env file
VECTOR_PROVIDER=elasticsearch
VECTOR_URL=http://localhost:9200
RAG_ENABLE_HYBRID_SEARCH=false

# Start Elasticsearch
docker run -p 9200:9200 -e "discovery.type=single-node" elasticsearch:8.7.0
```

### Hybrid Search with Reranking
```bash
# .env file  
VECTOR_PROVIDER=elasticsearch
VECTOR_URL=http://localhost:9200
RAG_ENABLE_HYBRID_SEARCH=true
HYBRID_ENABLED=true
HYBRID_RERANKER_ENABLED=true
HYBRID_RERANKER_API_KEY=your-cohere-key  # Optional for reranking
```

### Pinecone Cloud
```bash
# .env file
VECTOR_PROVIDER=pinecone
VECTOR_API_KEY=your-pinecone-key
VECTOR_ENVIRONMENT=us-east-1-aws
RAG_ENABLE_HYBRID_SEARCH=false
```

## Summary

- **Pinecone**: Cloud-hosted, pure vector search, easiest setup
- **Elasticsearch**: Self-hosted, pure vector search, no external deps
- **Hybrid**: Best search quality, requires Elasticsearch + optional Cohere

Choose based on your infrastructure preferences and search quality requirements.

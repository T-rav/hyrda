# Elasticsearch Setup for AI Slack Bot

This guide helps you set up Elasticsearch as a replacement for Pinecone in your AI Slack Bot.

## Quick Start

1. **Start Elasticsearch with Docker:**
   ```bash
   docker compose -f docker-compose.elasticsearch.yml up -d
   ```

2. **Verify Elasticsearch is running:**
   ```bash
   curl http://localhost:9200/_cluster/health
   ```

3. **Test the integration:**
   ```bash
   python test_elasticsearch_integration.py
   ```

4. **Update your .env file:**
   ```bash
   # Replace Pinecone settings with Elasticsearch
   VECTOR_PROVIDER=elasticsearch
   VECTOR_URL=http://localhost:9200
   # Remove: VECTOR_API_KEY (not needed for local Elasticsearch)
   # Remove: VECTOR_ENVIRONMENT (not needed for local Elasticsearch)
   ```

## What's Changed

### ✅ Added
- **ElasticsearchVectorStore** class with full vector search capabilities
- **Docker Compose** configuration for local Elasticsearch
- **Same embeddings** support (OpenAI text-embedding-3-small, 1536 dimensions)
- **Cosine similarity** search matching Pinecone behavior
- **Automatic index creation** with proper vector mappings

### 🔄 Updated
- **VectorSettings** now defaults to "elasticsearch" provider
- **Factory function** includes Elasticsearch option
- **Dependencies** added elasticsearch>=8.0.0

### 🗑️ To Remove
- Pinecone dependency (after testing)
- Pinecone-related environment variables

## Key Features

- **Local Development**: No API keys or external services needed
- **Vector Search**: Uses Elasticsearch dense_vector with cosine similarity
- **Same Interface**: Drop-in replacement for existing vector store code
- **Metadata Support**: Full metadata indexing and filtering
- **Bulk Operations**: Efficient document ingestion and deletion

## Configuration Options

```bash
# Elasticsearch settings
VECTOR_PROVIDER=elasticsearch
VECTOR_URL=http://localhost:9200           # Local Elasticsearch
VECTOR_COLLECTION_NAME=knowledge_base      # Index name

# For production Elasticsearch cluster
VECTOR_URL=https://your-es-cluster:9200
VECTOR_API_KEY=your_api_key                # If authentication needed
```

## Migration from Pinecone

1. **Keep existing embeddings** - no need to re-embed documents
2. **Re-ingest documents** using the new Elasticsearch vector store
3. **Same similarity thresholds** and search parameters work
4. **Remove Pinecone environment variables** from .env

## Troubleshooting

**Connection issues:**
- Make sure Docker is running: `docker ps`
- Check Elasticsearch health: `curl http://localhost:9200/_cat/health`

**Memory issues:**
- Elasticsearch uses 512MB by default in our Docker setup
- Increase if needed by modifying `ES_JAVA_OPTS` in docker-compose.elasticsearch.yml

**Index issues:**
- View indices: `curl http://localhost:9200/_cat/indices`
- Delete index: `curl -X DELETE http://localhost:9200/knowledge_base`

# Elasticsearch Setup for AI Slack Bot

This guide helps you set up Elasticsearch as a replacement for Pinecone in your AI Slack Bot, with full health monitoring integration.

## Quick Start

1. **Start Elasticsearch with Docker:**
   ```bash
   docker compose -f docker-compose.elasticsearch.yml up -d
   ```

2. **Verify Elasticsearch is running:**
   ```bash
   curl http://localhost:9200/_cluster/health
   ```

3. **Update your .env file:**
   ```bash
   # Replace Pinecone settings with Elasticsearch
   VECTOR_PROVIDER=elasticsearch
   VECTOR_URL=http://localhost:9200
   # Remove: VECTOR_API_KEY (not needed for local Elasticsearch)  
   # Remove: VECTOR_ENVIRONMENT (not needed for local Elasticsearch)
   ```

4. **Start your bot and verify setup:**
   ```bash
   cd bot && python app.py
   ```

5. **Monitor setup via Health Dashboard:**
   - Open `http://localhost:8080/ui`
   - Verify all services show as "Healthy" in the dashboard
   - Check that LLM service shows proper model configuration
   - Confirm cache and metrics are working properly

6. **Test the integration (optional):**
   ```bash
   python test_elasticsearch_integration.py
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
- **Health Monitoring**: Full integration with bot health dashboard
- **Auto-Configuration**: Automatic index creation and mapping setup

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

## Health Dashboard Integration

### 🎯 **Monitor Your Setup**

The bot's health dashboard at `http://localhost:8080/ui` provides comprehensive monitoring:

#### **Service Status Cards**
- **🟢 LLM API**: Shows provider (OpenAI/Anthropic) and model info
- **🟢 Cache**: Redis memory usage and cached conversations  
- **🟢 Langfuse**: Observability service status and host
- **🟢 Metrics**: Active conversations and Prometheus availability

#### **System Information**
- **Application**: Version (from `pyproject.toml`) and health status
- **System Uptime**: Live uptime counter with last update timestamp
- **API Endpoints**: Quick access to `/api/health`, `/api/metrics`, `/api/prometheus`

#### **Auto-Refresh**
- **⚡ Real-time updates** every 10 seconds
- **Manual refresh** button available
- **Smart error handling** with detailed troubleshooting info

## Troubleshooting

### **🔍 Quick Diagnostics**

1. **Check Health Dashboard First**: `http://localhost:8080/ui`
   - Look for any 🔴 red status indicators
   - Check detailed error messages in cards
   - Verify all services show as "Healthy"

2. **Verify Elasticsearch Container:**
   ```bash
   # Check if container is running
   docker ps | grep elasticsearch

   # Check container logs
   docker logs insightmesh-elasticsearch

   # Verify health endpoint
   curl http://localhost:9200/_cluster/health | jq
   ```

3. **Test Vector Store Connection:**
   ```bash
   # From your project root
   python -c "
   from config.settings import VectorSettings
   from services.vector_service import create_vector_store
   settings = VectorSettings()
   store = create_vector_store(settings)
   print(f'✅ Connected to {settings.provider} at {settings.url}')
   "
   ```

### **🐛 Common Issues**

#### **❌ "Connection refused" or service unavailable**
- **Dashboard shows**: 🔴 LLM API service error
- **Fix**:
  ```bash
  # Start Elasticsearch if not running
  docker compose -f docker-compose.elasticsearch.yml up -d

  # Wait 30 seconds for startup, then restart bot
  cd bot && python app.py
  ```

#### **❌ "Index not found" or search errors**  
- **Dashboard shows**: Normal services but search fails
- **Fix**: Re-run document ingestion:
  ```bash
  cd ingest && python main.py
  ```

#### **❌ Elasticsearch memory issues**
- **Dashboard shows**: Services healthy but slow responses  
- **Fix**: Increase Elasticsearch memory:
  ```yaml
  # In docker-compose.elasticsearch.yml
  ES_JAVA_OPTS: "-Xms1g -Xmx1g"  # Increase from 512m
  ```

#### **❌ Wrong vector provider in .env**
- **Dashboard shows**: 🔴 Various service errors
- **Fix**: Verify `.env` configuration:
  ```bash
  # Must be exactly:
  VECTOR_PROVIDER=elasticsearch
  VECTOR_URL=http://localhost:9200
  ```

### **🛠️ Advanced Debugging**

#### **Elasticsearch Cluster Info**
```bash
# Cluster health and stats
curl http://localhost:9200/_cluster/health?pretty
curl http://localhost:9200/_cluster/stats?pretty

# View all indices
curl http://localhost:9200/_cat/indices?v

# Check specific index mapping
curl http://localhost:9200/knowledge_base/_mapping?pretty
```

#### **Reset and Clean Start**
```bash
# Stop everything
docker compose -f docker-compose.elasticsearch.yml down -v

# Clean start (removes all data)
docker compose -f docker-compose.elasticsearch.yml up -d

# Wait for startup, then re-ingest documents
cd ingest && python main.py

# Restart bot
cd ../bot && python app.py
```

### **📊 Performance Monitoring**

- **Health Dashboard**: Monitor active conversations and memory usage
- **Prometheus Metrics**: Access at `http://localhost:8080/api/prometheus`
- **Elasticsearch Stats**: `curl http://localhost:9200/_nodes/stats?pretty`

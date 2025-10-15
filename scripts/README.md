# Vector Database Management Scripts

Simple, clear scripts to manage your Qdrant vector database.

## 🛠️ Initialize Indices

**Note**: Qdrant collections are initialized automatically on first use.

```bash
# Check initialization info
python scripts/init_indices.py
```

**What it does:**
- ✅ Provides information about automatic initialization
- ✅ Shows next steps for getting started

## 🔧 Configuration

Configuration is handled through your `.env` file:

```bash
# Qdrant Configuration
VECTOR_PROVIDER=qdrant
VECTOR_HOST=qdrant  # Docker service name or localhost
VECTOR_PORT=6333
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base
VECTOR_API_KEY=your-qdrant-api-key  # Optional

# Embedding model
EMBEDDING_MODEL=text-embedding-3-small  # 1536 dimensions
```

## 🚀 Typical Workflow

```bash
# 1. Start services
docker compose up -d

# 2. Run ingestion (creates collections automatically)
cd ingest && python main.py --folder-id "YOUR_FOLDER_ID"

# 3. Start bot
make run
```

## 🆘 Troubleshooting

**"Cannot connect to Qdrant":**
```bash
# Start Qdrant
docker compose up -d

# Check if running
docker ps | grep qdrant

# Test connection
curl http://localhost:6333
```

**"VECTOR_HOST not found":**
- Check your `.env` file exists
- Ensure Qdrant configuration is set

**"Collection errors":**
- Collections are created automatically
- Check Qdrant logs: `docker logs qdrant`
- Verify credentials if using authentication

These scripts are designed to be simple, safe, and clear about what they're doing.

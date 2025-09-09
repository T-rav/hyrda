# Vector Database Management Scripts

Simple, clear scripts to manage your Pinecone and Elasticsearch vector databases.

## 🧹 Clear Pinecone

**Purpose**: Delete all vectors from your Pinecone index for clean re-ingestion.

```bash
# Clear all vectors from Pinecone
python scripts/clear_pinecone.py

# Or run with venv
./venv/bin/python scripts/clear_pinecone.py
```

**What it does:**
- ✅ Connects to your Pinecone index using `.env` settings
- ✅ Shows current vector count
- ✅ Asks for confirmation before deletion
- ✅ Deletes all vectors safely
- ✅ Ready for fresh ingestion

**When to use:**
- Before re-ingesting documents with new settings
- When testing different embedding models
- When you want a completely clean slate

## 🛠️ Initialize Indices

**Purpose**: Create or recreate vector database indices with proper schemas.

```bash
# Initialize both Pinecone and Elasticsearch
python scripts/init_indices.py

# Force recreate (deletes existing data)
python scripts/init_indices.py --force

# Initialize only Pinecone
python scripts/init_indices.py --pinecone-only

# Initialize only Elasticsearch  
python scripts/init_indices.py --elasticsearch-only
```

**What it does:**
- ✅ Auto-detects your embedding model dimensions
- ✅ Creates Pinecone index with correct schema
- ✅ Creates Elasticsearch indices for BM25 search
- ✅ Handles both sparse and dense configurations
- ✅ Shows clear status and next steps

**When to use:**
- First-time setup of your vector databases
- After changing embedding models
- When you need to recreate indices with new schemas

## 🔧 Configuration

Both scripts read from your `.env` file:

```bash
# Required for Pinecone
VECTOR_API_KEY=your-pinecone-api-key
VECTOR_COLLECTION_NAME=insightmesh-knowledge-base
VECTOR_ENVIRONMENT=us-east-1

# Required for Elasticsearch
VECTOR_URL=http://localhost:9200

# Auto-detected embedding model
EMBEDDING_MODEL=text-embedding-3-large  # 3072 dimensions
```

## 🚀 Typical Workflow

```bash
# 1. Start services
./start_dependencies.sh

# 2. Clear existing data (optional)
python scripts/clear_pinecone.py

# 3. Initialize indices
python scripts/init_indices.py

# 4. Run ingestion
cd ingest && python main.py --folder-id "YOUR_FOLDER_ID"

# 5. Start bot
./start_bot.sh
```

## 🆘 Troubleshooting

**"Pinecone package not installed":**
```bash
./venv/bin/pip install pinecone
```

**"Cannot connect to Elasticsearch":**
```bash
docker compose -f docker-compose.elasticsearch.yml up -d
```

**"VECTOR_API_KEY not found":**
- Check your `.env` file exists
- Ensure `VECTOR_API_KEY=your-pinecone-key` is set

These scripts are designed to be simple, safe, and clear about what they're doing. They'll ask for confirmation before any destructive operations.

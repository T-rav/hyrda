# Developer Experience (DX) Setup

This directory contains local development tooling to enhance your workflow. **Nothing here affects production** - this is purely local dev infrastructure.

## What's Inside

### Milvus Vector Database (`milvus/`)

Local vector database for semantic code search via Claude Code's MCP (Model Context Protocol) integration.

## Claude Code Semantic Search Setup

### Prerequisites

1. **Node.js** 20.x to 23.x (required for claude-context MCP server)
2. **OpenAI API Key** (for code embeddings)
3. **Milvus running locally** (see below)

### Step 1: Start Milvus

```bash
cd dx/milvus
docker compose up -d

# Verify it's running
curl http://localhost:9091/healthz
# Should return: "OK"
```

### Step 2: Configure Claude Code MCP Server

Install the `claude-context` MCP server with local Milvus:

```bash
# From anywhere on your machine
claude mcp add claude-context \
  -e OPENAI_API_KEY=sk-your-openai-api-key \
  -e MILVUS_ADDRESS=http://localhost:19530 \
  -- npx @zilliz/claude-context-mcp@latest
```

**Environment Variables:**
- `OPENAI_API_KEY`: Your OpenAI API key (for embeddings)
- `MILVUS_ADDRESS`: Local Milvus endpoint (default: `http://localhost:19530`)

### Step 3: Index the Codebase

In Claude Code, run:
```
Index this codebase for semantic search
```

This will:
- Scan all code files in the repository
- Generate embeddings using OpenAI
- Store vectors in your local Milvus instance

**Note**: Initial indexing may take 5-10 minutes for large codebases.

### Step 4: Search Semantically

Now you can use natural language queries:

```
Find all authentication-related functions
Show me where we handle Google Drive OAuth
Find the RAG retrieval implementation
Locate error handling for task execution
```

## Available MCP Tools

Once configured, Claude Code has access to:

### `index_codebase`
- Indexes the current repository for semantic search
- Uses hybrid search (BM25 + dense vectors)
- Automatically handles file watching and incremental updates

### `search_code`
- Semantic search using natural language queries
- Returns relevant code snippets with context
- Faster than grep/glob for conceptual searches

### `get_indexing_status`
- Check indexing progress
- View collection stats

### `clear_index`
- Clear the indexed codebase
- Useful for starting fresh

## How It Works

```
┌─────────────────┐
│   Claude Code   │
│                 │
│  "Find auth     │
│   functions"    │
└────────┬────────┘
         │
         │ MCP Protocol
         ▼
┌─────────────────────────┐
│  claude-context server  │
│  (npx @zilliz/...)      │
│                         │
│  1. Embed query         │──► OpenAI API
│  2. Vector search       │──► Milvus (localhost:19530)
│  3. Return code chunks  │
└─────────────────────────┘
```

## Verification

Check if MCP server is registered:

```bash
# View Claude Code MCP configuration
cat ~/.config/claude/mcp.json
# or
cat ~/Library/Application\ Support/claude/mcp.json  # macOS
```

You should see an entry for `claude-context` with your environment variables.

## Troubleshooting

### "Cannot connect to Milvus"

```bash
# Ensure Milvus is running
cd dx/milvus
docker compose ps

# Check health
curl http://localhost:9091/healthz
```

### "Indexing is slow"

- Initial indexing is slower (generates embeddings for all files)
- Subsequent updates are incremental
- Consider using smaller `EMBEDDING_MODEL` if needed

### "MCP server not found"

```bash
# Verify Node.js version
node --version  # Should be 20.x - 23.x

# Re-add the MCP server
claude mcp remove claude-context
claude mcp add claude-context \
  -e OPENAI_API_KEY=sk-your-key \
  -e MILVUS_ADDRESS=http://localhost:19530 \
  -- npx @zilliz/claude-context-mcp@latest
```

### "OpenAI API quota exceeded"

Indexing a large codebase generates many embedding requests. Consider:
- Using a smaller embedding model
- Excluding certain directories (node_modules, venv, etc.)
- Checking OpenAI API limits

## Cost Considerations

**Embeddings Cost**: Indexing uses OpenAI's embedding API:
- `text-embedding-3-small`: ~$0.02 per 1M tokens
- Typical codebase (10K files, 500K LOC): ~$0.10-0.50 to index
- Incremental updates are cheap (only changed files)

**Alternative**: Use local embedding models with Ollama (requires MCP server modification).

## Cleanup

To remove everything:

```bash
# Stop Milvus
cd dx/milvus
docker compose down -v  # -v removes volumes (wipes data)

# Remove MCP server
claude mcp remove claude-context
```

## Resources

- [Claude Context MCP Server](https://github.com/zilliztech/claude-context)
- [Milvus Documentation](https://milvus.io/docs)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## Alternative: Qdrant MCP Server

If you prefer to use the existing Qdrant instance (already running in main docker-compose):

```bash
# Official Qdrant MCP server
claude mcp add code-search \
  -e QDRANT_URL="http://localhost:6333" \
  -e COLLECTION_NAME="insightmesh-code" \
  -- uvx mcp-server-qdrant
```

**Trade-offs:**
- **Qdrant**: Reuses existing infrastructure, simpler
- **Milvus (claude-context)**: More features, better for large codebases, actively maintained MCP integration

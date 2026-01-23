# Milvus Local Vector Database

Local Milvus instance for semantic code search via the claude-context MCP server.

## What is This?

Milvus is a vector database that powers semantic code search for Claude Code. This setup runs Milvus standalone locally, eliminating the need for Zilliz Cloud.

## Services

- **milvus-standalone** (port 19530): Vector database server
- **milvus-minio** (ports 9000, 9001): Object storage backend
- **milvus-etcd**: Configuration store

## Quick Start

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f standalone

# Stop services
docker compose down

# Stop and remove volumes (wipes all data)
docker compose down -v
```

## Endpoints

- **Milvus API**: `http://localhost:19530` (for MCP server)
- **Milvus Web UI**: `http://localhost:9091/webui/`
- **MinIO Console**: `http://localhost:9001` (minioadmin/minioadmin)

## Data Storage

All data is stored in `./volumes/`:
- `./volumes/milvus/` - Vector database data
- `./volumes/minio/` - Object storage
- `./volumes/etcd/` - Configuration

**Note**: These directories are created automatically and gitignored.

## Health Checks

```bash
# Check Milvus health
curl http://localhost:9091/healthz

# Check MinIO health
curl http://localhost:9000/minio/health/live
```

## Troubleshooting

**Container won't start:**
```bash
# Clean restart
docker compose down -v
docker compose up -d
```

**Port conflicts:**
If ports 19530, 9091, 9000, or 9001 are in use, edit `docker-compose.yml` to use different ports.

**View detailed logs:**
```bash
docker compose logs standalone
docker compose logs minio
docker compose logs etcd
```

## Resources

- [Milvus Documentation](https://milvus.io/docs)
- [Milvus GitHub](https://github.com/milvus-io/milvus)

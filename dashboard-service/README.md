# Dashboard Service

System-wide health and metrics dashboard for InsightMesh.

## Purpose

Aggregates metrics and health status from all services:
- **Bot** - Slack integration metrics
- **Agent Service** - LangGraph agent invocations
- **Tasks** - Scheduled job status
- **Control Plane** - Admin UI and permissions

## Endpoints

### Health & Metrics
- `GET /health` - Dashboard service health
- `GET /api/metrics` - Aggregated metrics from all services
- `GET /api/services/health` - Health status of all services
- `GET /api/agent-metrics` - Agent-specific metrics

### UI
- `GET /` or `/ui` - React dashboard interface

## Local Development

```bash
cd dashboard-service
pip install -e ".[dev]"
python app.py
```

Visit: http://localhost:8080

## Docker

```bash
docker compose up -d dashboard
```

## Architecture

```
Dashboard Service (port 8080)
    │
    ├─> Bot (8080) - Internal health endpoints
    ├─> Agent Service (8000)
    ├─> Tasks (8081)
    └─> Control Plane (6001)
```

Dashboard aggregates metrics via HTTP from each service's `/api/metrics` endpoint.

## Benefits

- **Single View** - All system metrics in one place
- **Service Independence** - Each service can restart independently
- **Clean Separation** - Dashboard concerns separated from business logic
- **Scalable** - Can add new services easily

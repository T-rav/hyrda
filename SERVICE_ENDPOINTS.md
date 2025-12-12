# InsightMesh Service Endpoints

## Core Services

### 1. Bot Service (insightmesh-bot)
- **Container**: insightmesh-bot
- **Image**: insightmesh-bot:latest (2.54GB)
- **Internal Port**: 8080 (metrics only, not exposed externally)
- **Description**: AI Slack bot with RAG capabilities
- **Dependencies**: MySQL, Qdrant, Redis, Agent Service

### 2. Agent Service (insightmesh-agent-service)
- **Container**: insightmesh-agent-service
- **Image**: insightmesh-agent-service:latest (1.59GB)
- **External Port**: 8000 (configurable via AGENT_SERVICE_PORT)
- **URL**: http://localhost:8000
- **Description**: LangGraph agent execution service
- **Dependencies**: MySQL, Qdrant, Redis
- **Volume Mounts**: ./external_agents:/app/external_agents:ro

### 3. Control Plane (insightmesh-control-plane)
- **Container**: insightmesh-control-plane
- **Image**: insightmesh-control-plane:latest (1.13GB)
- **External Port**: 6001 (configurable via CONTROL_PLANE_PORT)
- **URL**: https://localhost:6001 (HTTPS with SSL)
- **Description**: Admin UI and permissions management
- **Dependencies**: MySQL, Redis
- **Volume Mounts**: ./control_plane/ssl:/app/ssl:ro

### 4. Tasks Service (insightmesh-tasks)
- **Container**: insightmesh-tasks
- **Image**: insightmesh-tasks:latest (2.57GB)
- **External Ports**:
  - HTTP: 80
  - HTTPS: 5001 (configurable via TASKS_PORT)
- **URL**: https://localhost:5001 (HTTPS with SSL)
- **Description**: Task scheduler with OAuth and job management
- **Dependencies**: MySQL, Qdrant
- **Volume Mounts**:
  - ./tasks/ssl:/etc/nginx/ssl:ro
  - ./external_tasks:/app/external_tasks:ro

### 5. Dashboard Service (insightmesh-dashboard)
- **Container**: insightmesh-dashboard
- **Image**: insightmesh-dashboard:latest (583MB)
- **External Port**: 8080
- **URL**: http://localhost:8080
- **Description**: System-wide monitoring dashboard
- **Dependencies**: Bot, Agent Service, Tasks, Control Plane

## Data Services

### 6. MySQL Database
- **Container**: insightmesh-mysql
- **Image**: mysql:8.0
- **External Port**: 3306
- **URL**: mysql://root:password@localhost:3306
- **Databases**:
  - insightmesh_data
  - insightmesh_task
  - insightmesh_security
  - insightmesh_system

### 7. phpMyAdmin
- **Container**: insightmesh-phpmyadmin
- **External Port**: 8081
- **URL**: http://localhost:8081
- **Description**: Database management UI

### 8. Qdrant Vector Database
- **Container**: insightmesh-qdrant
- **Image**: qdrant/qdrant:latest
- **External Ports**:
  - REST API + Dashboard: 6333
  - gRPC API: 6334
- **URL**: http://localhost:6333
- **Dashboard**: http://localhost:6333/dashboard

### 9. Redis Cache
- **Container**: insightmesh-redis
- **Image**: redis:7-alpine
- **External Port**: 6379
- **URL**: redis://localhost:6379

## Observability Services

### 10. Loki (Log Aggregation)
- **Container**: insightmesh-loki
- **Image**: grafana/loki:latest
- **External Port**: 3100
- **URL**: http://localhost:3100
- **Description**: Centralized log storage

### 11. Promtail (Log Shipper)
- **Container**: insightmesh-promtail
- **Image**: grafana/promtail:latest
- **Description**: Collects logs from Docker containers and ships to Loki

### 12. Jaeger (Distributed Tracing)
- **Container**: insightmesh-jaeger
- **Image**: jaegertracing/all-in-one:latest
- **External Ports**:
  - UI: 16686
  - OTLP gRPC: 4317
  - OTLP HTTP: 4318
- **URL**: http://localhost:16686
- **Description**: OpenTelemetry-compatible tracing backend

## Monitoring Stack (docker-compose.monitoring.yml)

### 13. Prometheus (Metrics Collection)
- **Container**: insightmesh-prometheus
- **Image**: prom/prometheus:latest
- **External Port**: 9090 (configurable via PROMETHEUS_PORT)
- **URL**: http://localhost:9090
- **Description**: Metrics scraping and storage

### 14. Grafana (Visualization)
- **Container**: insightmesh-grafana
- **Image**: grafana/grafana:latest
- **External Port**: 3000 (configurable via GRAFANA_PORT)
- **URL**: http://localhost:3000
- **Credentials**: admin/admin
- **Description**: Unified dashboard for logs and metrics

### 15. AlertManager (Alerting)
- **Container**: insightmesh-alertmanager
- **Image**: prom/alertmanager:latest
- **External Port**: 9093
- **URL**: http://localhost:9093
- **Description**: Alert routing and management

## Quick Access Summary

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:8080 | System overview |
| Tasks UI | https://localhost:5001 | Task scheduler |
| Control Plane | https://localhost:6001 | Admin UI |
| Agent Service | http://localhost:8000 | Agent API |
| phpMyAdmin | http://localhost:8081 | Database UI |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector DB UI |
| Grafana | http://localhost:3000 | Logs + Metrics |
| Prometheus | http://localhost:9090 | Metrics |
| Jaeger | http://localhost:16686 | Traces |
| AlertManager | http://localhost:9093 | Alerts |

## Make Commands

```bash
# Start everything
make start                    # Full stack with monitoring

# Build and manage
make docker-build            # Build all images
make docker-up               # Start core services only
make docker-monitor          # Start monitoring stack
make stop                    # Stop everything
make restart                 # Restart everything
make status                  # Show container status

# Development
make test                    # Run all unit tests
make lint                    # Lint and format code
make quality                 # Complete quality pipeline

# Database
make db-start                # Start MySQL
make db-upgrade              # Apply migrations
make db-status               # Check migration status
make db-setup-system         # Setup system database
```

## Environment Variables

Key environment variables (see .env.example):

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# LLM
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Vector DB
VECTOR_HOST=qdrant
VECTOR_PORT=6333
VECTOR_API_KEY=...

# MySQL
MYSQL_ROOT_PASSWORD=changeme_root_password
MYSQL_TASKS_PASSWORD=changeme_tasks_password
MYSQL_DATA_PASSWORD=changeme_data_password
MYSQL_SECURITY_PASSWORD=changeme_security_password
MYSQL_SYSTEM_PASSWORD=changeme_system_password

# Service Tokens
BOT_SERVICE_TOKEN=...
CONTROL_PLANE_SERVICE_TOKEN=...

# OAuth
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
SERVER_BASE_URL=https://localhost:5001
CONTROL_PLANE_BASE_URL=https://localhost:6001

# Observability
LANGFUSE_ENABLED=false
LANGSMITH_API_KEY=...
```

## External Resources

### System vs External Split

**System Resources** (built into image, cannot be overridden):
- **System Agents**: `agent-service/agents/system/`
- **System Tasks**: `tasks/jobs/system/`
- Examples: research agent, security-audit agent, slack_user_import, gdrive_ingest

**External Resources** (client-customizable via volume mounts):
- **External Agents**: `./external_agents/` → `/app/external_agents:ro`
- **External Tasks**: `./external_tasks/` → `/app/external_tasks:ro`
- Examples: metric_sync, portal_sync, custom agents

**Override Protection**: External resources CANNOT override system resources. Conflicts are logged as errors and ignored.

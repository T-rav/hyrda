# 🔍 InsightMesh Observability Stack

Complete guide to monitoring, tracing, and debugging the InsightMesh system.

## 📊 Three Pillars of Observability

### 1. Distributed Tracing (Request Flow)
**Status**: ✅ Implemented
**Purpose**: Follow requests across services (Slack → Bot → Agent-Service)

**How it Works**:
- Every request gets a unique `trace_id` (format: `trace_12345678`)
- Trace IDs propagate via `X-Trace-Id` HTTP header
- All logs include `[trace_id]` prefix
- Middleware automatically adds trace IDs to all endpoints

**Usage**:
```bash
# Filter logs by trace_id to see complete request flow
docker logs insightmesh-bot 2>&1 | grep "trace_a1b2c3d4"
docker logs insightmesh-agent-service 2>&1 | grep "trace_a1b2c3d4"

# See request flow with timing
# [bot] Started -> [bot] LLM call (150ms) -> [agent-service] Started -> [agent-service] Success (250ms)
```

**Files**:
- `shared/utils/tracing.py` - Core tracing utilities
- `shared/middleware/tracing.py` - FastAPI middleware for automatic trace propagation
- `bot/services/agent_client.py` - Bot adds trace IDs to agent calls

### 2. LLM Observability (Langfuse)
**Status**: ✅ Active + Enhanced
**Purpose**: Track LLM calls, prompts, costs, latency

**What You Get**:
- Every LLM call logged to [Langfuse Cloud](https://us.cloud.langfuse.com)
- Automatic cost tracking (tokens × price)
- Prompt versioning and testing
- Performance analytics

**Enhanced with Trace IDs**:
- LLM calls now linked to request trace_ids
- In Langfuse UI, session_id = trace_id
- Can find "which Slack message triggered this LLM call"

**Configuration** (`.env`):
```bash
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

**Instrumented Functions**:
- `bot/services/llm_service.py:get_response()` - Main LLM calls
- `bot/services/query_rewriter.py` - Query rewriting, intent classification, HyDE
- `bot/services/rag_service.py` - RAG generation

**Files**:
- `shared/utils/langfuse_tracing.py` - Langfuse + trace ID integration
- `bot/services/llm_service.py` - Links LLM calls with trace_id

### 3. Application Metrics (Prometheus + Grafana)
**Status**: ✅ Fully Implemented
**Purpose**: Time-series metrics for monitoring and alerting

**What's Available**:
- Prometheus server running (port 9090)
- Grafana running (port 3000)
- HTTP metrics middleware integrated in all services
- `/metrics` endpoints on all services

**Collected Metrics**:
- `{service}_http_requests_total` - HTTP request counter (by method, endpoint, status_code)
- `{service}_http_request_duration_seconds` - HTTP request duration histogram (p50, p95, p99)
- `{service}_http_requests_in_progress` - Currently in-flight requests gauge
- `{service}_http_errors_total` - HTTP errors counter (by method, endpoint)

**Metrics Endpoints**:
- Agent-Service: `http://localhost:8000/metrics`
- Control-Plane: `http://localhost:6001/metrics`
- Tasks Service: `http://localhost:5001/metrics`

**Files**:
- `shared/middleware/prometheus_metrics.py` - Metrics middleware (integrated)
- `agent-service/services/metrics_service.py` - Agent-specific metrics
- `agent-service/app.py` - Integrated PrometheusMetricsMiddleware
- `control_plane/app.py` - Integrated PrometheusMetricsMiddleware
- `tasks/app.py` - Integrated PrometheusMetricsMiddleware

## 🔄 Complete Request Flow with Tracing

```
1. Slack Message Received
   └─ [trace_12345678] bot: message_received | user=U123

2. Bot Processes Message
   └─ [trace_12345678] bot: llm_call | duration=150ms
      ↓ Langfuse: session_id=trace_12345678, tokens=250, cost=$0.003

3. Bot Calls Agent-Service
   └─ [trace_12345678] bot: calling agent-service | agent=profile
      ↓ HTTP Header: X-Trace-Id: trace_12345678

4. Agent-Service Receives Request
   └─ [trace_12345678] agent-service: POST /api/agents/profile/invoke | started

5. Agent Executes
   └─ [trace_12345678] agent-service: agent_execution | duration=850ms | status=success

6. Response Returns to Bot
   └─ [trace_12345678] bot: response_sent | total_duration=1200ms
```

**Key Insight**: Every log line has `[trace_12345678]` so you can grep across all services!

## 📈 Monitoring Stack Components

| Component | Port | Status | Purpose |
|-----------|------|--------|---------|
| **Prometheus** | 9090 | ✅ Running | Metrics collection |
| **Grafana** | 3000 | ✅ Running | Metrics visualization |
| **Loki** | 3100 | ✅ Running | Log aggregation |
| **Promtail** | N/A | ✅ Running | Log shipping to Loki |
| **Langfuse** | Cloud | ✅ Active | LLM observability |
| **Alertmanager** | 9093 | ✅ Running | Alert management |

## 🛠️ How to Use

### Debug a Specific Request

1. **Find the trace_id** from bot logs:
```bash
docker logs insightmesh-bot 2>&1 | tail -100 | grep "trace_"
```

2. **Follow it across all services**:
```bash
trace_id="trace_12345678"
echo "=== BOT ===" && docker logs insightmesh-bot 2>&1 | grep "$trace_id"
echo "=== AGENT-SERVICE ===" && docker logs insightmesh-agent-service 2>&1 | grep "$trace_id"
```

3. **Find LLM calls for that request**:
- Go to [Langfuse Dashboard](https://us.cloud.langfuse.com)
- Filter by session_id = `trace_12345678`
- See all LLM calls, prompts, and costs

### Monitor System Health

1. **Check service metrics endpoints**:
```bash
# Agent-service HTTP metrics
curl http://localhost:8000/metrics

# Control-plane HTTP metrics
curl http://localhost:6001/metrics

# Tasks service HTTP metrics
curl http://localhost:5001/metrics
```

2. **Check Prometheus metrics**:
```bash
open http://localhost:9090
# Query examples:
#   rate(agent_service_http_requests_total[5m])
#   histogram_quantile(0.95, rate(control_plane_http_request_duration_seconds_bucket[5m]))
```

3. **View Grafana dashboards**:
```bash
open http://localhost:3000
# Default: admin/admin (change on first login)
```

4. **Query Loki logs**:
```bash
open http://localhost:3000/explore
# LogQL: {container="insightmesh-bot"} |= "error"
```

### Track LLM Costs

1. Go to [Langfuse Dashboard](https://us.cloud.langfuse.com)
2. Click "Traces" tab
3. See cost breakdown by:
   - User (session_id)
   - Model (gpt-4o vs gpt-4o-mini)
   - Time period

## 🚀 Next Steps (Future Enhancements)

### High Priority
1. ✅ ~~Add prometheus_client dependency~~ **DONE**
2. ✅ ~~Integrate PrometheusMetricsMiddleware~~ **DONE**
3. **Create Grafana dashboards**:
   - HTTP request rates and latency
   - Error rates by endpoint
   - Agent invocation metrics
4. **Set up alerts**:
   - Error rate > 5%
   - P99 latency > 5s
   - Service down

### Medium Priority
5. **Structured logging**: JSON format for easier parsing
6. **Log sampling**: Reduce log volume in production
7. **Trace sampling**: Only trace 10% of requests at scale

### Low Priority
8. **OpenTelemetry**: Migrate to OTLP for vendor-neutral observability
9. **Jaeger**: Add distributed tracing UI
10. **Custom metrics**: Business metrics (user satisfaction, agent success rate)

## 📚 Key Files

### Tracing
- `shared/utils/tracing.py` - Trace ID generation and propagation
- `shared/middleware/tracing.py` - FastAPI middleware
- `bot/services/agent_client.py` - Client-side trace propagation

### Langfuse Integration
- `shared/utils/langfuse_tracing.py` - Links Langfuse with trace IDs
- `bot/services/llm_service.py` - Instrumented with @observe

### Metrics (Ready to Use)
- `shared/middleware/prometheus_metrics.py` - HTTP metrics middleware
- `agent-service/services/metrics_service.py` - Application metrics

## 🎯 Production Readiness Checklist

- [x] Distributed tracing implemented
- [x] Trace IDs propagate across services
- [x] Langfuse tracking LLM calls
- [x] Langfuse linked with trace IDs
- [x] Prometheus + Grafana running
- [ ] Prometheus metrics exported by services
- [ ] Grafana dashboards configured
- [ ] Alerts configured
- [ ] Log retention policy set
- [ ] Metrics retention policy set

## 💡 Tips

1. **Always include trace_id in error reports**: Makes debugging 10x faster
2. **Check Langfuse daily**: Monitor LLM costs and quality
3. **Set up alerts early**: Don't wait for production issues
4. **Use trace_id for support**: When users report issues, ask them for the timestamp → find trace_id
5. **Correlate metrics with traces**: High latency? Find trace_id → see where time was spent

---

**Last Updated**: 2025-12-05
**Status**: Distributed Tracing ✅ | Langfuse ✅ | Prometheus ⚠️ (partial)

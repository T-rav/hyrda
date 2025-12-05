# Observability Backend Configuration

This guide shows how to swap observability backends without changing code.

## 🎯 Current Stack (Local Development)

- **Metrics**: Prometheus + Grafana
- **Traces**: Jaeger (OpenTelemetry)
- **Logs**: Loki + Promtail
- **LLM**: Langfuse

## 🔄 Swappable Components

### 1. Distributed Tracing (OpenTelemetry → Any Backend)

**Current: Jaeger (Local)**
```bash
# .env (default - no config needed)
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

**Swap to Datadog**:
```bash
# .env
OTEL_EXPORTER_OTLP_ENDPOINT=https://trace-agent.datadoghq.com:4317
DD_API_KEY=your_datadog_api_key
```

**Swap to New Relic**:
```bash
# .env
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.nr-data.net:4317
OTEL_EXPORTER_OTLP_HEADERS=api-key=your_newrelic_license_key
```

**Swap to Honeycomb**:
```bash
# .env
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io:443
OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=your_api_key
```

**Swap to AWS X-Ray**:
```bash
# .env
OTEL_EXPORTER_OTLP_ENDPOINT=http://xray-daemon:2000
AWS_REGION=us-east-1
```

**Disable Tracing**:
```bash
# .env
OTEL_TRACES_ENABLED=false
```

### 2. Metrics (Prometheus → Any Backend)

**Current: Prometheus + Grafana**
- Metrics exposed at `/metrics` endpoints
- Prometheus scrapes every 15s

**Swap to Datadog** (keeps Prometheus format):
```yaml
# docker-compose.yml - Add Datadog agent
datadog-agent:
  image: datadog/agent:latest
  environment:
    - DD_API_KEY=your_key
    - DD_SITE=datadoghq.com
    - DD_PROMETHEUS_SCRAPE_ENABLED=true
  volumes:
    - ./datadog.yaml:/etc/datadog-agent/conf.d/prometheus.d/conf.yaml
```

```yaml
# datadog.yaml
init_config:
instances:
  - prometheus_url: http://agent-service:8000/metrics
    namespace: insightmesh
  - prometheus_url: http://control-plane:6001/metrics
    namespace: insightmesh
  - prometheus_url: http://tasks:8001/metrics
    namespace: insightmesh
```

**Swap to New Relic**:
```bash
# Use Prometheus remote write
# Add to prometheus.yml:
remote_write:
  - url: https://metric-api.newrelic.com/prometheus/v1/write?prometheus_server=insightmesh
    authorization:
      credentials: your_newrelic_license_key
```

**Swap to AWS CloudWatch**:
- Use AWS Distro for OpenTelemetry (ADOT) collector
- Scrapes Prometheus endpoints → CloudWatch Metrics

### 3. Logs (Loki → Any Backend)

**Current: Loki + Promtail**
- Promtail ships Docker logs to Loki

**Swap to Datadog Logs**:
```yaml
# docker-compose.yml
datadog-agent:
  image: datadog/agent:latest
  environment:
    - DD_API_KEY=your_key
    - DD_LOGS_ENABLED=true
    - DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL=true
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - /var/lib/docker/containers:/var/lib/docker/containers:ro
```

**Swap to AWS CloudWatch Logs**:
- Use awslogs Docker log driver
- Or Fluent Bit sidecar

**Swap to Splunk**:
- Use Splunk Universal Forwarder
- Or Fluentd with Splunk output

### 4. LLM Observability

**Current: Langfuse**
```bash
# .env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

**Swap to LangSmith**:
```python
# bot/services/llm_service.py
# Replace: from langfuse.decorators import observe
# With:    from langsmith import traceable

# Replace: @observe(name="llm_service_response")
# With:    @traceable(name="llm_service_response")
```

```bash
# .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
```

**Swap to Weights & Biases**:
```python
# Similar decorator pattern, import from wandb
```

## 🚀 Production Recommendations

### Option 1: All-in-One (Easiest)
Use Datadog for everything:
- Traces: Auto-instrumentation via OTLP
- Metrics: Prometheus autodiscovery
- Logs: Docker log collection
- Keep Langfuse for LLM-specific observability

**Cost**: ~$15-30/host/month

### Option 2: Open Source (Free)
Keep current stack:
- Traces: Jaeger
- Metrics: Prometheus + Grafana
- Logs: Loki
- LLM: Langfuse (self-hosted)

**Cost**: Infrastructure only

### Option 3: Best-of-Breed
- Traces: Datadog or New Relic
- Metrics: Datadog or Prometheus
- Logs: Datadog or Splunk
- LLM: Langfuse Cloud

## 📝 Migration Checklist

When swapping backends:

- [ ] Update environment variables
- [ ] Test trace collection (make a request, check backend)
- [ ] Verify metrics scraping (check backend for metrics)
- [ ] Confirm logs flowing (check backend for recent logs)
- [ ] Update dashboards/queries for new backend
- [ ] Update alerting rules
- [ ] Document new backend URL and access

## 🔗 Backend URLs

### Local (Default)
- Jaeger UI: http://localhost:16686
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Langfuse: https://us.cloud.langfuse.com

### Enterprise
- Datadog: https://app.datadoghq.com
- New Relic: https://one.newrelic.com
- Honeycomb: https://ui.honeycomb.io
- Splunk: https://your-instance.splunkcloud.com

## 💡 Pro Tips

1. **Run multiple backends in parallel** during migration (dual-write traces/metrics)
2. **Test with sampling** - Start with 10% of traffic, ramp to 100%
3. **Keep Prometheus endpoints** - They're vendor-neutral and always useful
4. **Use OTLP format** - Works with all major observability vendors
5. **Tag everything** - service.name, environment, version for easy filtering

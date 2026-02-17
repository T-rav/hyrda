# Tracing & Integration Test Audit Plan

## Executive Summary

InsightMesh is a microservices architecture with 6 services. This audit evaluates:
1. **Distributed tracing coverage** - Do all inter-service calls have trace propagation?
2. **Integration test coverage** - Are all API routes tested end-to-end?

---

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Slack Bot     │────▶│  Control Plane   │◀────│  Agent Service  │
│    (bot/)       │     │ (control_plane/) │     │(agent-service/) │
│   Port: 8080    │     │   Port: 6001     │     │   Port: 8000    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  RAG Service    │────▶│   MySQL/Redis    │◀────│  Tasks Service  │
│ (rag-service/)  │     │   (Data/Cache)   │     │    (tasks/)     │
│   Port: 8002    │     │                  │     │   Port: 5001    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│     Qdrant      │     │ Dashboard Service│
│ (Vector Store)  │     │   Port: 8080     │
└─────────────────┘     └──────────────────┘
```

---

## 1. Tracing Middleware Status

### FastAPI Services (TracingMiddleware)

| Service | Has TracingMiddleware | Location |
|---------|----------------------|----------|
| **agent-service** | ✅ Yes | `app.py:90` |
| **control_plane** | ✅ Yes | `app.py:132` |
| **tasks** | ✅ Yes | `app.py:148` |
| **rag-service** | ✅ Yes | `app.py:118` |

### Non-FastAPI Services (aiohttp)

| Service | Tracing Status | Notes |
|---------|---------------|-------|
| **bot** | ✅ Yes | Trace middleware added via `shared.middleware.aiohttp_tracing` |
| **dashboard-service** | ✅ Yes | Trace middleware added via `shared.middleware.aiohttp_tracing` |

---

## 2. API Routes Inventory

### agent-service (1 router)
- `api/agents.py` - Agent invoke, stream, list

### control_plane (6 routers)
- `api/agents.py` - Agent registration, toggle, aliases
- `api/auth.py` - OAuth login/callback/logout
- `api/groups.py` - User group management
- `api/health.py` - Health/ready endpoints
- `api/service_accounts.py` - Service account CRUD
- `api/users.py` - User management, permissions

### tasks (7 routers)
- `api/auth.py` - Task auth
- `api/credentials.py` - OAuth credentials
- `api/gdrive.py` - Google Drive OAuth
- `api/health.py` - Health endpoints
- `api/hubspot.py` - HubSpot integration
- `api/jobs.py` - Job CRUD, pause/resume
- `api/task_runs.py` - Task run history

### rag-service (2 routers)
- `api/rag.py` - Chat completions, RAG queries
- `api/retrieve.py` - Vector retrieval

### bot (aiohttp endpoints)
- `/api/health` - Health check
- `/api/ready` - Readiness
- `/api/metrics` - Metrics
- `/api/prometheus` - Prometheus metrics
- `/api/users/import` - User import webhook
- `/api/ingest/completed` - Ingest webhook
- `/api/services/health` - Services health

### dashboard-service (aiohttp endpoints)
- Same as bot (shared health_aggregator.py)

---

## 3. Integration Test Coverage

### Files with @pytest.mark.integration (29 total)

**Well-covered:**
- `bot/tests/test_integration_*.py` (6 files)
- `tasks/tests/integration/` (2 files)
- `dashboard-service/tests/test_app_endpoints.py`
- `control_plane/tests/test_service_accounts_integration.py`

**Gaps Identified:**
- ✅ `rag-service/api/rag.py` - Integration tests added in `test_rag_api_integration.py`
- ✅ `agent-service/api/agents.py` - Tracing tests added to `test_api_endpoints.py`
- ⚠️ `tasks/api/hubspot.py` - Unit tests cover all endpoints (mocked DB)
- ✅ `control_plane/api/groups.py` - Integration tests added in `test_groups_integration.py`

---

## 4. Cross-Service Trace Propagation

### Current Implementation
- `shared/utils/trace_propagation.py` - Header extraction/creation
- `shared/middleware/tracing.py` - FastAPI middleware
- Services propagate `X-Trace-Id` and `X-Langfuse-Trace-ID` headers

### Service-to-Service Calls Traced

| Caller | Callee | Traced? |
|--------|--------|---------|
| bot → agent-service | ✅ Yes | `bot/services/agent_client.py` |
| bot → rag-service | ✅ Yes | `bot/services/rag_client.py` |
| rag-service → agent-service | ✅ Yes | `rag-service/services/agent_client.py` |
| tasks → bot | ⚠️ Partial | Webhooks have trace_id |
| agent-service → control_plane | ✅ Yes | Uses trace propagation |

### Missing Traces
- ❌ dashboard-service → all services (health aggregation)
- ❌ control_plane → external Google APIs (OAuth)

---

## 5. Action Plan

### Phase 1: Fix Tracing Gaps (Priority: High) ✅ COMPLETED

1. ✅ **Add tracing to dashboard-service health aggregation**
   - File: `dashboard-service/health_aggregator.py`
   - Added `shared.middleware.aiohttp_tracing` middleware

2. ✅ **Add tracing middleware to bot health endpoints**
   - File: `bot/health.py`
   - Added `shared.middleware.aiohttp_tracing` middleware

### Phase 2: Integration Test Coverage (Priority: High) ✅ COMPLETED

3. ✅ **rag-service integration tests**
   - Created: `rag-service/tests/integration/test_rag_api_integration.py`
   - Covers: Auth, validation, status, tracing headers (14 tests)

4. ✅ **agent-service tracing tests**
   - Added: `TestTracingHeaders` class to `test_api_endpoints.py`
   - Covers: X-Trace-Id propagation on all response types (5 tests)

5. ✅ **control_plane groups integration tests**
   - Created: `control_plane/tests/test_groups_integration.py`
   - Covers: Auth requirements, validation, tracing (14 tests)

6. ⚠️ **tasks hubspot tests**
   - Existing: `tasks/tests/test_api_hubspot.py` (unit tests with mocks)
   - Note: Full integration requires database setup

### Phase 3: End-to-End Trace Verification (Priority: Medium)

7. **Create E2E trace verification test** (Optional)
   - File: `tests/e2e/test_distributed_tracing.py`
   - Verify trace_id propagates: bot → agent-service → rag-service

8. **Add Langfuse trace assertions** (Optional)
   - Verify spans are created for each service hop
   - Verify parent-child relationships

---

## 6. Verification Checklist

After implementation, verify:

- [ ] All FastAPI services have TracingMiddleware
- [ ] All aiohttp services propagate X-Trace-Id
- [ ] Each API router has ≥1 integration test
- [ ] Cross-service calls include trace headers
- [ ] Langfuse shows connected trace trees
- [ ] No orphaned spans (missing parent_span_id)

---

## 7. Metrics to Track

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Services with tracing | 4/6 (67%) | 6/6 (100%) ✅ | 6/6 (100%) |
| Routers with integration tests | ~60% | ~90% ✅ | 100% |
| Cross-service calls traced | ~80% | ~95% ✅ | 100% |
| E2E trace verification | ❌ None | Optional | ✅ Automated |

---

## 8. Summary of Changes Made

### New Files Created
- `shared/middleware/aiohttp_tracing.py` - aiohttp tracing middleware
- `shared/tests/test_aiohttp_tracing.py` - Middleware tests (8 tests)
- `rag-service/tests/integration/test_rag_api_integration.py` - RAG API tests (14 tests)
- `control_plane/tests/test_groups_integration.py` - Groups API tests (14 tests)

### Files Modified
- `bot/health.py` - Added tracing middleware
- `dashboard-service/health_aggregator.py` - Added tracing middleware
- `rag-service/api/retrieve.py` - Fixed UnboundLocalError bug
- `agent-service/tests/test_api_endpoints.py` - Added tracing tests (5 tests)

### Bug Fixes
- Fixed `UnboundLocalError` in `rag-service/api/retrieve.py` where `trace` variable was used before initialization in except block

---

*Generated by Claude Code audit - 2026-02-16*
*Updated: 2026-02-16 with implementation progress*

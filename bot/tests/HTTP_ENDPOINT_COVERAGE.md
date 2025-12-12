# HTTP Endpoint Test Coverage Analysis

**Generated:** 2025-12-12
**Status:** 🟡 Partial Coverage - Only **14 of 80+ endpoints tested**

---

## 📊 Coverage Summary

| Service | Total Endpoints | Tested | Untested | Coverage |
|---------|----------------|--------|----------|----------|
| Bot (8080) | 16 | 3 | 13 | **19%** |
| RAG Service (8002) | 10 | 2 | 8 | **20%** |
| Agent Service (8000) | 8 | 2 | 6 | **25%** |
| Control Plane (6001) | 35+ | 2 | 33+ | **~6%** |
| Tasks Service (5001) | 20+ | 1 | 19+ | **~5%** |
| **TOTAL** | **80+** | **10** | **70+** | **~12%** |

---

## 🟢 Currently Tested Endpoints

### Bot Service (8080)
- ✅ `GET /api/health` - Basic health check
- ✅ `GET /api/ready` - Readiness probe
- ✅ `GET /api/services/health` - Multi-service health check

### RAG Service (8002)
- ✅ `POST /api/v1/chat/completions` - Generate RAG-enhanced responses (tested with multiple scenarios)
- ✅ `GET /health` - Health check

### Agent Service (8000)
- ✅ `GET /api/agents` - List available agents
- ✅ `POST /api/agents/{agent_name}/invoke` - Invoke agent (tested with auth)

### Control Plane (6001)
- ✅ `GET /health` - Health check
- ✅ `GET /api/users/{user_id}/permissions` - Get user permissions (partially)

### Tasks Service (5001)
- ✅ `GET /health` - Health check

---

## 🔴 Untested Endpoints (Gaps)

### Bot Service (8080) - 13 Endpoints Missing

**Metrics & Monitoring:**
- ❌ `GET /api/metrics` - JSON metrics endpoint
- ❌ `GET /api/prometheus` - Prometheus metrics
- ❌ `GET /api/metrics/usage` - Usage metrics
- ❌ `GET /api/metrics/performance` - Performance metrics
- ❌ `GET /api/metrics/errors` - Error metrics

**Webhook Endpoints (Critical for cross-service communication):**
- ❌ `POST /api/users/import` - Accept user imports from tasks service
- ❌ `POST /api/ingest/completed` - Accept ingestion completion notifications
- ❌ `POST /api/metrics/store` - Store metrics from tasks service

**UI Endpoints:**
- ❌ `GET /ui` - Health dashboard UI
- ❌ `GET /` - Root (health dashboard)

**Legacy Endpoints:**
- ❌ `GET /health` - Legacy health
- ❌ `GET /ready` - Legacy readiness
- ❌ `GET /metrics` - Legacy metrics

---

### RAG Service (8002) - 8 Endpoints Missing

**Health & Monitoring:**
- ❌ `GET /api/health` - Aliased health
- ❌ `GET /ready` - Readiness probe with dependencies
- ❌ `GET /api/ready` - Aliased readiness
- ❌ `GET /api/metrics` - JSON metrics
- ❌ `GET /metrics` - Prometheus metrics
- ❌ `GET /prometheus` - Prometheus endpoint

**Status & Info:**
- ❌ `GET /api/v1/status` - RAG service status
- ❌ `GET /` - Service info

**Alternative Endpoints:**
- ❌ `POST /api/chat/completions` - Alias without v1 prefix

---

### Agent Service (8000) - 6 Endpoints Missing

**Monitoring:**
- ❌ `GET /health` - Health check
- ❌ `GET /api/metrics` - Agent invocation metrics
- ❌ `GET /metrics` - Prometheus metrics

**Agent Management:**
- ❌ `GET /` - Service info and agent list
- ❌ `GET /api/agents/{agent_name}` - Get agent metadata
- ❌ `POST /api/agents/{agent_name}/stream` - Streaming agent invocation

---

### Control Plane (6001) - 33+ Endpoints Missing

**Authentication (5 endpoints):**
- ❌ `GET /auth/login` - Initiate OAuth login
- ❌ `GET /auth/callback` - OAuth callback
- ❌ `GET /auth/token` - Get JWT token
- ❌ `POST /auth/logout` - Logout user
- ❌ `GET /api/health` - Aliased health

**User Management (7 endpoints):**
- ❌ `GET /api/users/me` - Get current user info
- ❌ `GET /api/users` - List all users (paginated)
- ❌ `POST /api/users/sync` - Sync users from provider
- ❌ `PUT /api/users/{user_id}/admin` - Update admin status
- ❌ `POST /api/users/{user_id}/permissions` - Grant agent permission
- ❌ `DELETE /api/users/{user_id}/permissions` - Revoke agent permission
- ❌ `GET /metrics` - Prometheus metrics

**Group Management (9 endpoints):**
- ❌ `GET /api/groups` - List groups
- ❌ `POST /api/groups` - Create group
- ❌ `PUT /api/groups/{group_name}` - Update group
- ❌ `DELETE /api/groups/{group_name}` - Delete group
- ❌ `GET /api/groups/{group_name}/users` - List group members
- ❌ `POST /api/groups/{group_name}/users` - Add user to group
- ❌ `DELETE /api/groups/{group_name}/users` - Remove user from group
- ❌ `GET /api/groups/{group_name}/agents` - List agents for group
- ❌ `POST /api/groups/{group_name}/agents` - Assign agent to group
- ❌ `DELETE /api/groups/{group_name}/agents` - Revoke agent from group

**Agent Management (6 endpoints):**
- ❌ `GET /api/agents` - List registered agents
- ❌ `POST /api/agents/register` - Register new agent
- ❌ `GET /api/agents/{agent_name}` - Get agent details
- ❌ `DELETE /api/agents/{agent_name}` - Delete agent
- ❌ `GET /api/agents/{agent_name}/usage` - Get agent usage stats
- ❌ `POST /api/agents/{agent_name}/toggle` - Enable/disable agent

**UI Routes:**
- ❌ `GET /` - React UI root
- ❌ `GET /{path:path}` - SPA catch-all routes

---

### Tasks Service (5001) - 19+ Endpoints Missing

**Authentication (3 endpoints):**
- ❌ `GET /api/auth/me` - Get current user
- ❌ `GET /api/auth/callback` - OAuth callback
- ❌ `POST /api/auth/logout` - Logout

**Job Management (11 endpoints):**
- ❌ `GET /api/scheduler/info` - Scheduler status
- ❌ `GET /api/jobs` - List all jobs
- ❌ `GET /api/jobs/{job_id}` - Get job details
- ❌ `POST /api/jobs` - Create scheduled job
- ❌ `PUT /api/jobs/{job_id}` - Update job
- ❌ `POST /api/jobs/{job_id}/pause` - Pause job
- ❌ `POST /api/jobs/{job_id}/resume` - Resume job
- ❌ `DELETE /api/jobs/{job_id}` - Delete job
- ❌ `POST /api/jobs/{job_id}/retry` - Retry failed job
- ❌ `POST /api/jobs/{job_id}/run-once` - Run job once
- ❌ `GET /api/jobs/{job_id}/history` - Job execution history
- ❌ `GET /api/job-types` - List job types

**Google Drive (3 endpoints):**
- ❌ `POST /api/gdrive/auth/initiate` - Start Google Drive OAuth
- ❌ `GET /api/gdrive/auth/callback` - Google OAuth callback
- ❌ `GET /api/gdrive/auth/status/{task_id}` - Get auth status

**Credentials (2 endpoints):**
- ❌ `GET /api/credentials` - List credentials
- ❌ `DELETE /api/credentials/{cred_id}` - Delete credential

**Task Runs (1 endpoint):**
- ❌ `GET /api/task_runs` - List task execution runs

**Monitoring (2 endpoints):**
- ❌ `GET /api/health` - Aliased health
- ❌ `GET /metrics` - Prometheus metrics

---

## 🎯 Critical Gaps (High Priority)

### 1. **Cross-Service Webhooks (Not Tested)**
These are critical for microservice communication:
- ❌ `POST /api/users/import` (bot) - Tasks → Bot communication
- ❌ `POST /api/ingest/completed` (bot) - Tasks → Bot notifications
- ❌ `POST /api/metrics/store` (bot) - Tasks → Bot metrics

**Impact:** Integration failures between tasks service and bot won't be caught.

### 2. **Authentication Flows (Not Tested)**
OAuth and JWT flows completely untested:
- ❌ Control Plane OAuth endpoints (`/auth/login`, `/auth/callback`, `/auth/token`)
- ❌ Tasks OAuth endpoints (`/api/auth/*`)

**Impact:** User authentication failures won't be caught.

### 3. **User & Permission Management (Not Tested)**
Core RBAC functionality untested:
- ❌ User CRUD operations (`GET /api/users`, `POST /api/users/sync`)
- ❌ Permission management (`POST/DELETE /api/users/{id}/permissions`)
- ❌ Group management (entire `/api/groups/*` hierarchy)

**Impact:** Authorization and access control bugs won't be detected.

### 4. **Agent Registration & Discovery (Partially Tested)**
Agent lifecycle management gaps:
- ✅ `GET /api/agents` (tested)
- ❌ `POST /api/agents/register` (not tested)
- ❌ `DELETE /api/agents/{name}` (not tested)
- ❌ `POST /api/agents/{name}/toggle` (not tested)

**Impact:** Agent registration/deregistration failures won't be caught.

### 5. **Job Scheduling & Management (Not Tested)**
Entire tasks service scheduling system untested:
- ❌ All `/api/jobs/*` endpoints
- ❌ Google Drive integration (`/api/gdrive/*`)
- ❌ Credential management (`/api/credentials/*`)

**Impact:** Scheduled ingestion jobs (critical feature) completely untested.

### 6. **Prometheus Metrics Endpoints (Not Tested)**
Observability gaps:
- ❌ All `/metrics` and `/prometheus` endpoints across services

**Impact:** Monitoring and alerting system integration untested.

### 7. **Streaming Responses (Not Tested)**
- ❌ `POST /api/agents/{name}/stream` (agent-service)

**Impact:** Real-time streaming agent responses untested.

---

## 📋 Recommended Test Priorities

### Phase 1: Critical Business Logic (Highest Priority)
1. **Webhook Endpoints** - Cross-service communication
   - `POST /api/users/import`
   - `POST /api/ingest/completed`
   - `POST /api/metrics/store`

2. **Job Management** - Core scheduling feature
   - `POST /api/jobs` - Create job
   - `GET /api/jobs` - List jobs
   - `POST /api/jobs/{id}/run-once` - Trigger job
   - `GET /api/jobs/{id}/history` - Job execution history

3. **Agent Registration** - Service discovery
   - `POST /api/agents/register`
   - `GET /api/agents/{name}` - Get metadata
   - `POST /api/agents/{name}/toggle` - Enable/disable

### Phase 2: Authentication & Authorization
4. **OAuth Flows** - User authentication
   - Control Plane OAuth endpoints
   - Tasks OAuth endpoints

5. **Permission Management** - RBAC
   - `POST /api/users/{id}/permissions` - Grant permission
   - `DELETE /api/users/{id}/permissions` - Revoke permission
   - `GET /api/users` - List users

6. **Group Management** - Team permissions
   - `POST /api/groups` - Create group
   - `POST /api/groups/{name}/agents` - Assign agent to group

### Phase 3: Observability & Operations
7. **Metrics Endpoints** - Monitoring
   - `GET /api/metrics` (all services)
   - `GET /metrics` - Prometheus format

8. **Readiness Probes** - Deployment health
   - `GET /ready` (all services)
   - `GET /api/ready` (aliased)

9. **Status Endpoints** - Service info
   - `GET /api/v1/status` (rag-service)
   - `GET /api/scheduler/info` (tasks)

### Phase 4: Advanced Features
10. **Google Drive Integration**
    - `POST /api/gdrive/auth/initiate`
    - `GET /api/gdrive/auth/callback`

11. **Streaming Responses**
    - `POST /api/agents/{name}/stream`

12. **Credential Management**
    - `GET /api/credentials`
    - `DELETE /api/credentials/{id}`

---

## 🚀 Implementation Plan

### Step 1: Expand Integration Tests (1-2 days)
Create `test_integration_extended.py` with:
- Webhook endpoint tests (bot ← tasks)
- Agent registration tests (agent-service → control-plane)
- User permission tests (control-plane)
- Job management tests (tasks)

### Step 2: Add Authentication Tests (1 day)
Create `test_integration_auth.py` with:
- OAuth flow tests (mock OAuth provider)
- JWT token validation
- Permission checks

### Step 3: Add Metrics Tests (0.5 day)
Create `test_integration_metrics.py` with:
- Prometheus endpoint validation
- Metrics format verification
- All services metrics collection

### Step 4: Add Advanced Feature Tests (1 day)
Create `test_integration_advanced.py` with:
- Google Drive OAuth flow
- Streaming agent responses
- Credential CRUD operations

---

## 💡 Recommendations

1. **Start with Critical Business Logic** - Focus on webhooks and job management first (highest business impact)

2. **Use Contract Testing** - Consider Pact or similar for API contract tests between services

3. **Mock External Dependencies** - OAuth providers, Google Drive API for faster test execution

4. **Add OpenAPI/Swagger Validation** - Generate tests from OpenAPI specs to ensure coverage

5. **CI/CD Integration** - Run endpoint tests in staging environment before production deploy

6. **Separate Test Suites:**
   - Unit tests (current: 619 tests)
   - Integration tests (current: ~48 tests, need ~150+ more)
   - Contract tests (new: ~50 tests)
   - E2E tests (existing system flows: 14 tests)

---

## 📊 Target Coverage Goals

| Category | Current | Target | Gap |
|----------|---------|--------|-----|
| Core Business Logic | 25% | 100% | +75% |
| Authentication | 0% | 90% | +90% |
| Authorization | 6% | 90% | +84% |
| Monitoring | 20% | 80% | +60% |
| Cross-Service Webhooks | 0% | 100% | +100% |
| **Overall HTTP Endpoints** | **~12%** | **~85%** | **+73%** |

---

## ✅ Conclusion

The current integration tests provide **good coverage of happy path user flows** but miss:
- ❌ **70+ endpoints untested** (~88% of API surface)
- ❌ **Critical cross-service webhooks** (tasks → bot)
- ❌ **Entire authentication system** (OAuth, JWT)
- ❌ **Complete authorization system** (users, groups, permissions)
- ❌ **Scheduled job management** (core feature)
- ❌ **Observability endpoints** (metrics, Prometheus)

**Next Steps:**
1. Prioritize webhook and job management endpoint tests (highest business value)
2. Add authentication/authorization tests (security critical)
3. Expand to metrics and observability (operational critical)
4. Consider contract testing for service boundaries

---

**Generated:** 2025-12-12
**Status:** 🟡 Partial Coverage - Significant gaps identified

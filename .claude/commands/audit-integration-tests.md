# Integration Test Audit

Run a comprehensive integration test audit across all services. Launch one agent per service, all in parallel and in background. Each agent maps external dependencies in source code, inventories existing integration tests, identifies coverage gaps, flags ugly/outdated tests, and creates GitHub issues for findings (with duplicate checking).

## Instructions

1. Launch ALL of the following agents **in parallel** using `Task` with `run_in_background: true` and `subagent_type: "general-purpose"`.
2. Wait for all agents to complete.
3. After all finish, run `gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "integration test" --limit 200` to show the user a final summary of all issues created.

## Tier 1 Agents to Launch

### Agent 1: bot/ integration test audit
```
You are an integration test auditor for the bot/ service in /Users/travisf/Documents/projects/insightmesh.

## Goal
Identify what integration tests are missing to ensure the bot service operates correctly when Docker containers are built and running. Also flag ugly/outdated tests that should be pruned.

## Steps

### Phase 1: Map External Dependencies
1. Use Glob to list ALL .py files in bot/ — EXCLUDE .venv/, __pycache__/, node_modules/, *.pyc
2. Read all SOURCE files (not tests/) and catalog every external dependency:
   - HTTP calls to other microservices (agent-service, control-plane, rag-service, tasks)
   - Database calls (MySQL via SQLAlchemy)
   - Redis operations (sync and async)
   - Qdrant vector store operations
   - Slack API calls (slack_sdk)
   - External API calls (OpenAI, Tavily, Perplexity, Langfuse)
   For each dependency, note: file path, line number, method name, what it calls, what it expects back, error handling

### Phase 2: Inventory Existing Integration Tests
3. Read ALL test files. Catalog every test marked @pytest.mark.integration, @pytest.mark.smoke, or @pytest.mark.system_flow
4. For each existing integration test, note: what external dependency it actually exercises, whether it uses real services or mocks

### Phase 3: Gap Analysis
5. Cross-reference Phase 1 dependencies against Phase 2 test coverage
6. Identify external interaction paths with ZERO integration test coverage
7. Identify tests that claim to be "integration" but are fully mocked (false integration tests)

### Phase 4: Ugly/Outdated Test Detection
8. Flag these anti-patterns in integration tests:
   - "Always-pass" pattern: tests that catch connection errors and print "PASS" (defeating the purpose)
   - Fixture duplication: service_urls/http_client defined in every file instead of conftest
   - Hardcoded Docker service names that break local development
   - Tests using subprocess.run(["docker", ...]) that are fragile
   - Tests that accept ANY HTTP status code as passing (e.g., assert status in [200, 401, 403, 404, 500])
   - Dead tests: marked @pytest.mark.skip or calling pytest.skip() immediately
   - Ad-hoc test scripts in service root (not in tests/ directory)
   - Module-level sys.modules or sys.path hacks

### Phase 5: Create GitHub Issues
9. For each finding, check for duplicate GH issues first:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms from title>"
10. Create GH issues for NEW findings only. Group related gaps into single issues per theme:
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: <service> - <theme>" --body "<details>"

## Issue Body Format
Use this template for issue bodies:
```markdown
## Context
<1-2 sentences on why this integration test matters>

## External Dependencies Not Covered
| Dependency | File:Line | Method | What It Calls |
|------------|-----------|--------|---------------|
| <name> | <path:line> | <method> | <endpoint/operation> |

## Suggested Test Scenarios
- [ ] <scenario 1>
- [ ] <scenario 2>

## Ugly Tests to Prune (if applicable)
- <file:line> - <what's wrong>

## Notes
- Service: bot
- Priority: <high/medium/low based on blast radius>
```

## Grouping Strategy
Create ONE issue per theme, not one per missing test. Good themes:
- "Integration Test: bot - Service-to-service HTTP calls (agent-service, rag-service)"
- "Integration Test: bot - Redis caching round-trips"
- "Integration Test: bot - Qdrant vector operations"
- "Integration Test: bot - Prune always-pass integration tests"

Return a summary of all findings grouped by category, with GH issue URLs created.
```

### Agent 2: agent-service/ integration test audit
```
You are an integration test auditor for the agent-service/ service in /Users/travisf/Documents/projects/insightmesh.

## Goal
Identify what integration tests are missing to ensure the agent-service operates correctly when Docker containers are built and running. Also flag ugly/outdated tests that should be pruned.

## Steps

### Phase 1: Map External Dependencies
1. Use Glob to list ALL .py files in agent-service/ — EXCLUDE .venv/, __pycache__/, node_modules/, *.pyc
2. Read all SOURCE files (not tests/) and catalog every external dependency:
   - HTTP calls to control-plane (registration, agent registry)
   - Qdrant vector store operations
   - Redis operations (conversation cache, web search cache)
   - OpenAI API (embeddings, LLM chat completions with function calling)
   - Tavily/Perplexity search APIs
   - HubSpot CRM API
   - SEC EDGAR API
   - MinIO/S3 object storage
   - Slack API
   - YouTube Data API
   - Langfuse/LangSmith tracing
   For each dependency, note: file path, line number, method name, what it calls, what it expects back, error handling

### Phase 2: Inventory Existing Integration Tests
3. Read ALL test files including any in agent-service/agents/*/tests/. Catalog every test marked @pytest.mark.integration or @pytest.mark.smoke
4. For each existing integration test, note: what external dependency it actually exercises, whether it uses real services or mocks

### Phase 3: Gap Analysis
5. Cross-reference Phase 1 dependencies against Phase 2 test coverage
6. Identify external interaction paths with ZERO integration test coverage
7. Identify tests that claim to be "integration" but are fully mocked (false integration tests)

### Phase 4: Ugly/Outdated Test Detection
8. Flag these anti-patterns:
   - "integration" marker on fully mocked tests (misleading)
   - sys.path.insert() or sys.modules hacks at module level
   - Tests buried inside agents/ package instead of tests/ directory
   - Minimal test files (< 10 test functions for a complex module)
   - Missing streaming response path coverage
   - Thin coverage files (e.g., only 8 tests for a cache module)

### Phase 5: Create GitHub Issues
9. Check for duplicates first, then create issues grouped by theme:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: agent-service - <theme>" --body "<details>"

Use the same issue body format and grouping strategy as Agent 1.

Return a summary of all findings grouped by category, with GH issue URLs created.
```

### Agent 3: control_plane/ integration test audit
```
You are an integration test auditor for the control_plane/ service in /Users/travisf/Documents/projects/insightmesh.

## Goal
Identify what integration tests are missing to ensure the control plane operates correctly when Docker containers are built and running. Also flag ugly/outdated tests that should be pruned.

## Steps

### Phase 1: Map External Dependencies
1. Use Glob to list ALL .py files in control_plane/ — EXCLUDE .venv/, __pycache__/, node_modules/, *.pyc
2. Read all SOURCE files and catalog every external dependency:
   - MySQL via SQLAlchemy (security DB + data DB — two-database architecture)
   - Redis (service account caching, rate limiting, session middleware, JWT token storage)
   - HTTP to agent-service (metrics endpoint)
   - HTTP to LangSmith proxy (health check)
   - Slack SDK (users_lookupByEmail during OAuth callback, users_list for sync)
   - Google OAuth (token verification, flow creation)
   For each dependency, note: file path, line number, method name, what it calls, error handling

### Phase 2: Inventory Existing Integration Tests
3. Read ALL test files. Catalog every test marked @pytest.mark.integration or @pytest.mark.smoke
4. Note which tests use real services vs mocks vs SQLite-in-place-of-MySQL

### Phase 3: Gap Analysis
5. Cross-reference dependencies against test coverage
6. Pay special attention to:
   - Goal Bots API (api/goal_bots.py) — any coverage at all?
   - Redis session middleware for OAuth flow
   - Token refresh with real Redis
   - Two-database architecture (security DB + data DB simultaneously)
   - Service account Redis fallback path

### Phase 4: Ugly/Outdated Test Detection
8. Flag:
   - Permissive assertions (assert status in [200, 401, 403, 404])
   - CSS/HTML class name assertions in backend tests
   - Migration smoke tests that break without real MySQL
   - Leftover Flask→FastAPI migration regression guards
   - conftest.py missing GoalBot table cleanup
   - Fragile HTML template parsing in tests

### Phase 5: Create GitHub Issues
9. Check for duplicates, then create themed issues:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: control_plane - <theme>" --body "<details>"

Use the same issue body format and grouping strategy as Agent 1.

Return a summary of all findings grouped by category, with GH issue URLs created.
```

### Agent 4: tasks/ integration test audit
```
You are an integration test auditor for the tasks/ service in /Users/travisf/Documents/projects/insightmesh.

## Goal
Identify what integration tests are missing to ensure the tasks service operates correctly when Docker containers are built and running. Also flag ugly/outdated tests that should be pruned.

## Steps

### Phase 1: Map External Dependencies
1. Use Glob to list ALL .py files in tasks/ — EXCLUDE .venv/, __pycache__/, node_modules/, *.pyc, ui/
2. Read all SOURCE files and catalog every external dependency:
   - HTTP to rag-service (ingest client with fallback to direct)
   - HubSpot REST API (deals, companies, owners, pipelines)
   - Metric.ai GraphQL API (employees, projects, clients, allocations)
   - Google Drive API (list files, download, permissions)
   - Google OAuth2 (token refresh, web flow)
   - OpenAI Whisper (audio/video transcription)
   - OpenAI Embeddings
   - Qdrant vector store
   - SQLAlchemy (task DB + data DB)
   - subprocess: yt-dlp (YouTube download) and ffmpeg (audio chunking)
   - Website scraping via httpx + BeautifulSoup/Crawlee
   - Control plane JWT validation
   - Fernet encryption for OAuth credentials
   For each dependency, note: file path, line number, method name, what it calls, error handling

### Phase 2: Inventory Existing Integration Tests
3. Read ALL test files in tests/ and tests/integration/. Catalog every test marked @pytest.mark.integration or with pytest.skip()
4. Note which tests actually run vs are permanently skipped

### Phase 3: Gap Analysis
5. Cross-reference dependencies against test coverage
6. Pay special attention to:
   - RAG service HTTP client (zero coverage)
   - Google Drive OAuth callback and full ingestion pipeline
   - Encryption lifecycle (encrypt → store → decrypt at job time)
   - Token refresh in jobs
   - APScheduler job persistence across restart

### Phase 4: Ugly/Outdated Test Detection
8. Flag:
   - Tests in integration/ directory without @pytest.mark.integration marker
   - Permanently skipped tests (dead code)
   - Double-guarded tests (skipif + pytest.skip inside body)
   - Real time.sleep() in retry timing tests (30+ seconds)
   - Ad-hoc test scripts in service root (not in tests/)
   - Debug print() statements in production code found during review
   - integration_conftest.py with fixtures never used by any running test

### Phase 5: Create GitHub Issues
9. Check for duplicates, then create themed issues:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: tasks - <theme>" --body "<details>"

Use the same issue body format and grouping strategy as Agent 1.

Return a summary of all findings grouped by category, with GH issue URLs created.
```

### Agent 5: rag-service/ integration test audit
```
You are an integration test auditor for the rag-service/ service in /Users/travisf/Documents/projects/insightmesh.

## Goal
Identify what integration tests are missing to ensure the rag-service operates correctly when Docker containers are built and running. Also flag ugly/outdated tests and potential bugs.

## Steps

### Phase 1: Map External Dependencies
1. Use Glob to list ALL .py files in rag-service/ — EXCLUDE .venv/, __pycache__/, node_modules/, *.pyc
2. Read all SOURCE files and catalog every external dependency:
   - Qdrant vector store (initialize, search, add, delete, get_stats, get_collection_info)
   - OpenAI Embedding API
   - OpenAI LLM API (chat completions with function calling)
   - HTTP to agent-service (invoke, stream, list agents) with circuit breaker
   - Tavily search API
   - Perplexity deep research API
   - Redis conversation cache
   - HTTP to bot service (usage tracking)
   - Google OAuth token refresh
   - Langfuse tracing
   For each dependency, note: file path, line number, method name, what it calls, error handling

### Phase 2: Inventory Existing Integration Tests
3. Read ALL test files in tests/ and tests/integration/. Catalog every test marked @pytest.mark.integration or @pytest.mark.smoke
4. Note which are real integration tests vs mocked tests with the wrong marker

### Phase 3: Gap Analysis
5. Cross-reference dependencies against test coverage
6. Pay special attention to:
   - Qdrant live operations (upsert + search round-trip)
   - Agent client circuit breaker state transitions
   - HMAC signature verification on real POST requests
   - /ready endpoint with vector DB enabled (check for get_collection_info bug)
   - Chat completions end-to-end (currently @skip)
   - Retrieve endpoint end-to-end (currently @skip)

### Phase 4: Bug Detection
7. Check if get_collection_info() is called anywhere but not implemented on QdrantVectorStore (the base class has get_stats() but /ready and /status endpoints may call get_collection_info()). If confirmed, create a separate bug issue.

### Phase 5: Ugly/Outdated Test Detection
8. Flag:
   - Tests misnamed as "integration" that are pure unit tests
   - Deeply nested patch blocks (6+ levels of `with patch(...)`)
   - Duplicate test files covering the same endpoints
   - Incomplete smoke tests (only health, no actual operations)
   - Mixed markers in same file (unit + integration without separation)
   - Tests that require real API keys but have no skip guard

### Phase 6: Create GitHub Issues
9. Check for duplicates, then create themed issues:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: rag-service - <theme>" --body "<details>"

For any confirmed bugs, create a separate issue:
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Bug: rag-service - <description>" --body "<details>"

Use the same issue body format and grouping strategy as Agent 1.

Return a summary of all findings grouped by category, with GH issue URLs created.
```

### Agent 6: dashboard-service/ integration test audit
```
You are an integration test auditor for the dashboard-service/ service in /Users/travisf/Documents/projects/insightmesh.

## Goal
Identify what integration tests are missing to ensure the dashboard service operates correctly when Docker containers are built and running. Also flag ugly/outdated tests.

## Steps

### Phase 1: Map External Dependencies
1. Use Glob to list ALL .py files in dashboard-service/ — EXCLUDE .venv/, __pycache__/, node_modules/, *.pyc, health_ui/
2. Read all SOURCE files and catalog every external dependency:
   - HTTP to all 5 downstream services via aiohttp (bot, agent-service, control-plane, rag-service, tasks)
   - MySQL via pymysql (database health check)
   - Google OAuth (token verification, flow)
   - Langfuse stats API
   - Session middleware (itsdangerous)
   For each dependency, note: file path, line number, method name, what it calls, error handling

### Phase 2: Inventory Existing Integration Tests
3. Read ALL test files. Catalog tests marked @pytest.mark.integration
4. Note quality of mock setups (are aiohttp patches intercepting correctly?)

### Phase 3: Gap Analysis
5. Cross-reference dependencies against test coverage
6. Pay special attention to:
   - /api/agent-metrics (completely untested)
   - Bot metrics parsing in /api/ready
   - Database healthy path in services_health()
   - Auth callback happy path through actual FastAPI route
   - Cookie-based auth fallback (no SessionMiddleware)

### Phase 4: Ugly/Outdated Test Detection
8. Flag:
   - async def tests that run synchronously (TestClient is sync)
   - Incorrect aiohttp mock patches (patching wrong module path)
   - Vacuous assertions (assert status in [200, 307, 500])
   - Trivially weak auth endpoint assertions (only check != 404)
   - Module-level sys.modules mutation in conftest
   - No-op boolean type assertions
   - Missing shared fixtures (conftest nearly empty)

### Phase 5: Create GitHub Issues
9. Check for duplicates, then create themed issues:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: dashboard-service - <theme>" --body "<details>"

Use the same issue body format and grouping strategy as Agent 1.

Return a summary of all findings grouped by category, with GH issue URLs created.
```

### Agent 7: Cross-service & shared/ integration test audit
```
You are an integration test auditor for cross-service concerns and shared/ utilities in /Users/travisf/Documents/projects/insightmesh.

## Goal
Identify integration test gaps that span multiple services — things that only break when containers talk to each other. Also audit the shared/ library for integration gaps.

## Steps

### Phase 1: Map Cross-Service Integration Points
1. Read these key files to understand service-to-service contracts:
   - shared/utils/request_signing.py (HMAC signatures between services)
   - shared/middleware/redis_session.py (Redis session middleware used by control_plane)
   - shared/utils/jwt_auth.py (JWT token management used across services)
   - shared/services/langfuse_service.py (tracing propagation)
   - bot/tests/domains/conftest.py (existing cross-service test infrastructure)
   - bot/tests/test_integration_service_to_service.py
   - bot/tests/test_integration_microservices_strict.py
   - bot/tests/test_system_flows.py

### Phase 2: Identify Cross-Service Gaps
2. Check for missing tests of these inter-service flows:
   - Bot → RAG service: HMAC-signed request → signature verification → response
   - Bot → Agent service: service token auth → agent invocation → SSE streaming → response
   - Agent service → Control plane: agent registration on startup
   - Tasks → RAG service: document ingestion with auth
   - Tasks → Control plane: JWT validation for protected endpoints
   - Control plane → Agent service: metrics fetching
   - Dashboard → All services: health aggregation
   - Distributed trace propagation (X-Trace-Id flowing through service chain)
   - Redis session: OAuth state stored → callback reads → session created

### Phase 3: Audit Shared Utilities
3. Read shared/tests/ and check coverage of:
   - Migration integrity tests
   - Request signing (generate + verify round-trip)
   - JWT auth (create + verify + refresh + revoke with Redis)
   - Redis session middleware

### Phase 4: Infrastructure Gaps
4. Check for:
   - Missing docker-compose.test.yml for isolated integration testing
   - Missing `make test-integration` Makefile target
   - Inconsistent integration test directory structure across services
   - Missing shared conftest for service URL fixtures

### Phase 5: Create GitHub Issues
5. Check for duplicates, then create themed issues:
   gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<key terms>"
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: cross-service - <theme>" --body "<details>"

For infrastructure issues:
   gh issue create --repo 8thlight/insightmesh --assignee T-rav --label claude-find --title "Integration Test: infra - <theme>" --body "<details>"

Use the same issue body format and grouping strategy as the other agents.

Return a summary of all findings grouped by category, with GH issue URLs created.
```

## Important Notes
- Each agent should read files directly (no spawning sub-agents)
- Each agent should check `gh issue list --repo 8thlight/insightmesh --label claude-find --state open --search "<terms>"` before creating any issue to avoid duplicates
- All issues should use label `claude-find` and assignee `T-rav`
- Group related findings into single themed issues — don't create one issue per missing test
- Be pragmatic: external API tests (OpenAI, Tavily, HubSpot) are expensive; note them but mark as low priority. Focus on inter-service HTTP calls, DB, Redis, and Qdrant as high priority.
- Title format: "Integration Test: <service> - <theme>" for consistency
- For confirmed bugs found during audit, use title format: "Bug: <service> - <description>"

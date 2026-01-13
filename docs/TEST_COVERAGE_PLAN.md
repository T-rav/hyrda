# 🧪 Comprehensive Test Coverage Plan - InsightMesh Integration Tests

**Status:** 14/17 tests passing (82%) ✅
**Date:** 2025-12-12
**Architecture:** Microservices (bot, rag-service, agent-service, control-plane, tasks)

---

## 📊 Current Test Coverage Analysis

### ✅ What's Currently Tested

#### 1. **Service Health & Discovery** (COVERED)
- ✅ All 5 services health checks
- ✅ Service availability reporting
- ✅ Graceful handling when services down

#### 2. **Bot → RAG Service Communication** (COVERED)
- ✅ Basic query/response flow
- ✅ Conversation history handling
- ✅ Document content processing
- ✅ Vector database integration (RAG + Qdrant)
- ✅ Authentication requirements (401 handling)

#### 3. **Bot → Agent Service Communication** (COVERED)
- ✅ Agent discovery (list agents)
- ✅ Agent invocation with authentication
- ✅ 401 auth handling

#### 4. **Bot → Control Plane** (COVERED)
- ✅ Health checks
- ✅ Permissions endpoint discovery

#### 5. **Error Handling** (COVERED)
- ✅ Timeout scenarios
- ✅ Connection errors
- ✅ Service unavailable graceful handling
- ✅ End-to-end error flow

#### 6. **Performance** (COVERED)
- ✅ Concurrent request handling (5 parallel requests)

#### 7. **Cross-Service** (COVERED)
- ✅ Tasks → Bot communication patterns
- ✅ Service-to-service authentication

---

## 🎯 HAPPY PATH Test Coverage Plan

### Priority 1: Core User Flows (Must Have)

#### A. **Complete User Query Flow** ⭐⭐⭐
**Scenario:** User asks question → RAG retrieves context → LLM responds

**Tests Needed:**
```python
@pytest.mark.integration
@pytest.mark.happy_path
async def test_complete_user_query_with_rag_retrieval():
    """
    Test: User query → RAG → Qdrant → LLM → Response with citations

    Steps:
    1. Send query to bot service
    2. Bot calls rag-service with use_rag=True
    3. RAG service queries qdrant for context
    4. LLM generates response with citations
    5. Verify response has content + citations
    6. Verify response time < 5s
    """
    pass

@pytest.mark.integration
@pytest.mark.happy_path
async def test_multi_turn_conversation_flow():
    """
    Test: Multi-turn conversation maintains context

    Steps:
    1. Send initial query with context
    2. Send follow-up question
    3. Verify bot remembers previous context
    4. Verify conversation_history passed correctly
    """
    pass
```

#### B. **Agent-Based Workflows** ⭐⭐⭐
**Scenario:** User triggers specialized agent → Agent executes → Returns structured result

**Tests Needed:**
```python
@pytest.mark.integration
@pytest.mark.happy_path
async def test_research_agent_full_workflow():
    """
    Test: Research agent end-to-end

    Steps:
    1. User asks research question
    2. Bot routes to research agent
    3. Agent performs web search + analysis
    4. Agent returns structured findings
    5. Verify response format and content quality
    """
    pass

@pytest.mark.integration
@pytest.mark.happy_path
async def test_sql_agent_database_query():
    """
    Test: SQL agent generates and executes query

    Steps:
    1. User asks data question
    2. Bot routes to SQL agent
    3. Agent generates safe SQL query
    4. Agent executes against database
    5. Agent formats results
    6. Verify results accuracy
    """
    pass
```

#### C. **Document Upload & Processing** ⭐⭐
**Scenario:** User uploads document → Bot processes → Can answer questions about it

**Tests Needed:**
```python
@pytest.mark.integration
@pytest.mark.happy_path
async def test_pdf_upload_and_query():
    """
    Test: Upload PDF → Process → Query content

    Steps:
    1. Upload test PDF via Slack
    2. Bot extracts and chunks content
    3. User asks question about document
    4. Verify accurate response from document
    """
    pass

@pytest.mark.integration
@pytest.mark.happy_path
async def test_multiple_document_formats():
    """
    Test: Support for PDF, DOCX, XLSX, PPTX

    Steps:
    1. Upload each format type
    2. Verify successful processing
    3. Query content from each
    4. Verify accurate extraction
    """
    pass
```

#### D. **Scheduled Tasks & Background Jobs** ⭐⭐
**Scenario:** Scheduled task runs → Processes data → Notifies users

**Tests Needed:**
```python
@pytest.mark.integration
@pytest.mark.happy_path
async def test_google_drive_scheduled_ingestion():
    """
    Test: Scheduled Google Drive sync

    Steps:
    1. Trigger scheduled ingestion task
    2. Verify OAuth credential retrieval
    3. Verify file discovery and filtering
    4. Verify document processing pipeline
    5. Verify vector database updates
    6. Verify completion notification
    """
    pass

@pytest.mark.integration
@pytest.mark.happy_path
async def test_background_reindexing():
    """
    Test: Background vector database reindexing

    Steps:
    1. Trigger reindex task
    2. Verify no user-facing disruption
    3. Verify completion and health checks
    """
    pass
```

#### E. **Permissions & Access Control** ⭐⭐
**Scenario:** User access is properly controlled based on permissions

**Tests Needed:**
```python
@pytest.mark.integration
@pytest.mark.happy_path
async def test_user_permissions_enforcement():
    """
    Test: Permissions checked before sensitive operations

    Steps:
    1. User with permissions requests sensitive data
    2. Control-plane validates permissions
    3. Request proceeds successfully
    4. Verify proper audit logging
    """
    pass
```

---

### Priority 2: Data Flows (Should Have)

#### F. **RAG Pipeline End-to-End** ⭐⭐
```python
@pytest.mark.integration
@pytest.mark.happy_path
async def test_document_ingestion_to_retrieval():
    """
    Test: Document → Chunking → Embedding → Storage → Retrieval

    Steps:
    1. Ingest test document
    2. Verify chunking with proper overlap
    3. Verify embeddings generated
    4. Verify Qdrant storage
    5. Query for content
    6. Verify accurate retrieval with scores
    """
    pass
```

#### G. **Observability & Monitoring** ⭐
```python
@pytest.mark.integration
@pytest.mark.happy_path
async def test_distributed_tracing_full_request():
    """
    Test: Request traces through all services

    Steps:
    1. Send request with trace ID
    2. Verify trace propagates: bot → rag → agent → control-plane
    3. Verify Jaeger receives complete trace
    4. Verify span timing data
    """
    pass

@pytest.mark.integration
@pytest.mark.happy_path
async def test_metrics_collection_across_services():
    """
    Test: Prometheus metrics from all services

    Steps:
    1. Make requests to each service
    2. Verify metrics endpoints return data
    3. Verify key metrics present (latency, errors, requests)
    4. Verify Grafana dashboards queryable
    """
    pass
```

---

## ⚠️ EDGE CASES & UNHAPPY PATH Test Coverage Plan

### Priority 1: Error Handling & Resilience (Must Have)

#### A. **Service Failure Scenarios** ⭐⭐⭐
```python
@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_rag_service_down_graceful_degradation():
    """
    Test: RAG service unavailable → Graceful fallback

    Steps:
    1. Stop rag-service
    2. User sends query
    3. Verify graceful error message
    4. Verify no stack traces leaked
    5. Verify retry logic kicks in
    6. Verify circuit breaker activates
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_qdrant_unavailable_fallback():
    """
    Test: Vector DB down → Bot still responds (no RAG)

    Steps:
    1. Stop Qdrant
    2. User sends query
    3. Verify bot responds without RAG
    4. Verify user notified of limited functionality
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_partial_service_outage():
    """
    Test: One agent service down, others work

    Steps:
    1. Stop one specialized agent
    2. Verify other agents still available
    3. Verify graceful error for unavailable agent
    """
    pass
```

#### B. **Authentication & Authorization Failures** ⭐⭐⭐
```python
@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_invalid_service_token():
    """
    Test: Invalid X-Service-Token → 401 response

    Steps:
    1. Send request with invalid token
    2. Verify 401 Unauthorized
    3. Verify no sensitive data in error
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_missing_service_token():
    """
    Test: Missing token header → 401 response
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_user_lacks_permissions():
    """
    Test: User without permission → Access denied

    Steps:
    1. User without permission requests sensitive data
    2. Control-plane denies access
    3. Verify 403 Forbidden
    4. Verify audit log entry
    """
    pass
```

#### C. **Data Validation & Input Errors** ⭐⭐⭐
```python
@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_malformed_request_payload():
    """
    Test: Invalid JSON → 400 Bad Request

    Steps:
    1. Send malformed JSON to endpoints
    2. Verify 400 response
    3. Verify helpful error message
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_missing_required_fields():
    """
    Test: Missing user_id, query, etc → 422 Validation Error
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_sql_injection_prevention():
    """
    Test: SQL agent prevents injection attacks

    Steps:
    1. Send malicious SQL in query
    2. Verify safe query generation
    3. Verify no execution of injected code
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_xss_prevention_in_responses():
    """
    Test: Malicious script tags sanitized
    """
    pass
```

#### D. **Rate Limiting & Resource Exhaustion** ⭐⭐
```python
@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_concurrent_request_limit():
    """
    Test: Too many concurrent requests → 429 Rate Limited

    Steps:
    1. Send 100 concurrent requests
    2. Verify rate limiting activates
    3. Verify 429 responses after threshold
    4. Verify service remains stable
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_large_document_rejection():
    """
    Test: Document exceeds size limit → 413 Payload Too Large

    Steps:
    1. Upload 50MB document
    2. Verify rejection with clear error
    3. Verify service stability
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_memory_leak_long_conversation():
    """
    Test: Very long conversation doesn't leak memory

    Steps:
    1. Send 100+ messages in conversation
    2. Monitor memory usage
    3. Verify no unbounded growth
    """
    pass
```

#### E. **Timeout & Latency** ⭐⭐
```python
@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_llm_timeout_handling():
    """
    Test: LLM takes too long → Timeout with retry

    Steps:
    1. Mock slow LLM response (>30s)
    2. Verify timeout triggers
    3. Verify retry logic
    4. Verify eventual error message to user
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_slow_vector_search():
    """
    Test: Qdrant search slow → Fallback behavior
    """
    pass
```

---

### Priority 2: Data Integrity & Edge Cases (Should Have)

#### F. **Unusual Data Scenarios** ⭐⭐
```python
@pytest.mark.integration
@pytest.mark.edge_case
async def test_empty_document_upload():
    """
    Test: Empty file → Graceful error
    """
    pass

@pytest.mark.integration
@pytest.mark.edge_case
async def test_corrupted_file_upload():
    """
    Test: Corrupted PDF → Error with recovery
    """
    pass

@pytest.mark.integration
@pytest.mark.edge_case
async def test_unicode_emoji_in_query():
    """
    Test: Unicode handling in queries and responses

    Steps:
    1. Send query with emoji and special characters
    2. Verify proper handling
    3. Verify response preserves formatting
    """
    pass

@pytest.mark.integration
@pytest.mark.edge_case
async def test_very_long_query():
    """
    Test: 10,000 character query → Truncation or chunking
    """
    pass

@pytest.mark.integration
@pytest.mark.edge_case
async def test_conversation_with_no_history():
    """
    Test: First message in thread → No errors
    """
    pass
```

#### G. **Race Conditions & Concurrency** ⭐⭐
```python
@pytest.mark.integration
@pytest.mark.edge_case
async def test_simultaneous_document_uploads():
    """
    Test: Multiple users uploading at once → No conflicts
    """
    pass

@pytest.mark.integration
@pytest.mark.edge_case
async def test_concurrent_agent_invocations():
    """
    Test: Multiple agent calls simultaneously → All succeed
    """
    pass
```

#### H. **Database & Storage Failures** ⭐⭐
```python
@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_redis_cache_unavailable():
    """
    Test: Redis down → Degraded performance but still functional
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_mysql_connection_lost():
    """
    Test: MySQL down → Control-plane degrades gracefully
    """
    pass

@pytest.mark.integration
@pytest.mark.unhappy_path
async def test_qdrant_disk_full():
    """
    Test: Vector DB storage full → Error handling
    """
    pass
```

---

## 📈 Test Metrics & Success Criteria

### Test Coverage Goals
- ✅ **Happy Path:** 100% of core user flows (10/10 tests)
- ✅ **Unhappy Path:** 100% of critical error scenarios (15/15 tests)
- ✅ **Edge Cases:** 80% of identified edge cases (8/10 tests)

### Performance Targets
- ✅ P95 response time < 2s for simple queries
- ✅ P99 response time < 5s for RAG-enhanced queries
- ✅ System handles 100 concurrent users
- ✅ No memory leaks over 1000 requests

### Reliability Targets
- ✅ Service uptime > 99.9% (excluding planned maintenance)
- ✅ Graceful degradation when dependencies fail
- ✅ Circuit breaker activates within 3 failed requests
- ✅ Automatic recovery when services return

---

## 🚀 Implementation Priority

### Phase 1: Critical Coverage (Week 1)
1. Complete user query flow with RAG
2. Multi-turn conversation context
3. Service failure graceful degradation
4. Authentication error handling
5. Input validation & security (SQL injection, XSS)

### Phase 2: Core Functionality (Week 2)
6. Agent-based workflows (research, SQL)
7. Document upload & processing
8. Rate limiting & resource protection
9. Timeout handling
10. Database failure scenarios

### Phase 3: Edge Cases (Week 3)
11. Unusual data scenarios
12. Concurrency & race conditions
13. Performance under load
14. Observability & tracing
15. Scheduled tasks & background jobs

---

## 📝 Test Execution Plan

### Local Development
```bash
# Run all integration tests
pytest -v -m integration

# Run only happy path tests
pytest -v -m "integration and happy_path"

# Run only unhappy path tests
pytest -v -m "integration and unhappy_path"

# Run edge case tests
pytest -v -m "integration and edge_case"
```

### CI/CD Pipeline
1. **Pre-commit:** Unit tests only
2. **PR Branch:** Integration tests with mocked services
3. **Staging:** Full integration tests against real services
4. **Production:** Smoke tests + health checks

### Test Environment Requirements
- ✅ All services running via docker-compose
- ✅ Test data seeded in databases
- ✅ OAuth credentials configured for tasks
- ✅ Service tokens configured for auth
- ✅ Monitoring stack (Prometheus, Grafana, Jaeger)

---

**Next Steps:**
1. Review and approve this plan
2. Implement Phase 1 tests (Critical Coverage)
3. Set up CI/CD integration
4. Monitor coverage metrics in Grafana

# Code Quality Improvement Plan: HTTP Retrieval Client & Tools

## Executive Summary

Analysis of the HTTP retrieval implementation reveals **802 lines of duplicated code** and several architectural issues. This plan addresses code duplication, method size, abstraction quality, and testing gaps.

---

## 🔴 Critical Issues (P0 - Must Fix)

### 1. **Code Duplication (802 lines duplicated)**

**Problem**: Identical files copied between `agent-service` and `custom_agents/profiler`:
- `retrieval_client.py` (144 lines × 2 = 288 lines)
- `internal_search_http.py` (257 lines × 2 = 514 lines)

**Impact**:
- Bug fixes must be applied twice
- Maintenance burden doubled
- High risk of drift between copies
- Violates DRY principle

**Solution**: Move to `shared/` module
```
shared/
  clients/
    retrieval_client.py    # Centralized HTTP client
  tools/
    internal_search_http.py  # Centralized tool implementation
```

**Changes Required**:
```python
# Before (agent-service)
from services.retrieval_client import get_retrieval_client

# After (both services)
from shared.clients.retrieval_client import get_retrieval_client
```

**Effort**: 2-3 hours
**Risk**: Low (simple move + import updates)

---

## 🟠 High Priority Issues (P1 - Should Fix)

### 2. **Method Size - `retrieve()` Too Large (50 lines)**

**Problem**: Single method doing too much:
- Building payload (lines 84-99)
- Preparing headers (lines 101-106)
- JSON serialization (line 109)
- Adding signatures (line 112)
- HTTP call (lines 118-120)
- Response parsing (lines 122-131)

**Solution**: Extract smaller methods
```python
class RetrievalClient:
    async def retrieve(self, query: str, ...) -> list[dict[str, Any]]:
        """Main retrieval method - orchestrates the flow."""
        payload = self._build_payload(query, user_id, ...)
        headers = self._build_headers(user_id)
        signed_request = self._sign_request(payload, headers)
        response = await self._execute_request(signed_request)
        return self._parse_response(response)

    def _build_payload(self, ...) -> dict[str, Any]:
        """Build request payload (8-10 lines)."""
        ...

    def _build_headers(self, user_id: str) -> dict[str, str]:
        """Build request headers (5 lines)."""
        ...

    def _sign_request(self, payload: dict, headers: dict) -> SignedRequest:
        """Add HMAC signature (5 lines)."""
        ...

    async def _execute_request(self, request: SignedRequest) -> httpx.Response:
        """Execute HTTP request with retry logic (10 lines)."""
        ...

    def _parse_response(self, response: httpx.Response) -> list[dict[str, Any]]:
        """Parse and validate response (8 lines)."""
        ...
```

**Benefits**:
- Each method < 15 lines
- Clear single responsibility
- Easier to test
- Easier to extend (add retry, circuit breaker, etc.)

**Effort**: 3-4 hours
**Risk**: Medium (requires tests)

---

### 3. **Method Size - `_format_results()` Too Large (51 lines)**

**Problem**: Single formatting method doing multiple concerns:
- Grouping chunks by source (lines 149-163)
- Detecting relationships (line 166)
- Building relationship status (lines 171-177)
- Building summary header (lines 179-181)
- Formatting each document (lines 184-196)

**Solution**: Extract smaller formatters
```python
class InternalSearchToolHTTP(BaseTool):
    def _format_results(self, chunks: list[dict], query: str) -> str:
        """Main formatter - orchestrates formatting."""
        docs_by_source = self._group_by_source(chunks)
        has_relationship = self._detect_relationship(chunks)

        parts = [
            self._format_relationship_status(has_relationship),
            self._format_summary(query, chunks, docs_by_source),
            self._format_documents(docs_by_source),
        ]
        return "\n".join(parts)

    def _group_by_source(self, chunks: list[dict]) -> dict[str, list[dict]]:
        """Group chunks by source document (10 lines)."""
        ...

    def _format_relationship_status(self, has_relationship: bool) -> str:
        """Format relationship status header (5 lines)."""
        ...

    def _format_summary(self, query: str, chunks: list, docs: dict) -> str:
        """Format search summary (5 lines)."""
        ...

    def _format_documents(self, docs_by_source: dict) -> str:
        """Format document results (15 lines)."""
        ...
```

**Effort**: 2-3 hours
**Risk**: Low (pure refactoring)

---

### 4. **Missing Abstractions - Request/Response Models**

**Problem**: Using raw dicts for request/response
```python
# Current - untyped dicts
payload = {"query": query, "user_id": user_id, ...}
chunks = data.get("chunks", [])  # What's the shape of chunks?
```

**Solution**: Introduce Pydantic models
```python
# shared/clients/models.py
from pydantic import BaseModel, Field

class RetrievalRequest(BaseModel):
    """Request model for retrieval API."""
    query: str = Field(..., min_length=1)
    user_id: str = "agent@system"
    max_chunks: int = Field(10, ge=1, le=20)
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0)
    filters: dict[str, Any] | None = None
    conversation_history: list[dict[str, str]] | None = None
    enable_query_rewriting: bool = True

class Chunk(BaseModel):
    """Single retrieved chunk."""
    content: str
    similarity: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any]

class RetrievalResponse(BaseModel):
    """Response from retrieval API."""
    chunks: list[Chunk]
    metadata: dict[str, Any]

# In retrieval_client.py
async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
    payload = request.model_dump(exclude_none=True)
    ...
    return RetrievalResponse.model_validate(data)
```

**Benefits**:
- Type safety
- Validation at boundaries
- Self-documenting
- IDE autocomplete
- Easier to test

**Effort**: 4-5 hours
**Risk**: Medium (API contract change)

---

## 🟡 Medium Priority Issues (P2 - Nice to Have)

### 5. **Magic Strings and Numbers**

**Problem**: Hardcoded values scattered throughout
```python
user_id = user_id or "agent@system"  # What is agent@system?
base_url = "http://rag-service:8002"  # Why 8002?
timeout = 30.0  # Why 30 seconds?
default=0.7  # Why 0.7 threshold?
```

**Solution**: Configuration class
```python
# shared/clients/config.py
from dataclasses import dataclass

@dataclass(frozen=True)
class RetrievalClientConfig:
    """Configuration for retrieval client."""

    # Service discovery
    base_url: str = "http://rag-service:8002"

    # Authentication
    default_user_id: str = "agent@system"

    # Timeouts (seconds)
    request_timeout: float = 30.0
    connect_timeout: float = 5.0

    # Retrieval defaults
    default_max_chunks: int = 10
    default_similarity_threshold: float = 0.7

    # Retry policy
    max_retries: int = 3
    retry_backoff: float = 1.0

# In retrieval_client.py
class RetrievalClient:
    def __init__(self, config: RetrievalClientConfig | None = None):
        self.config = config or RetrievalClientConfig()
        ...
```

**Effort**: 2-3 hours
**Risk**: Low

---

### 6. **Error Handling - Too Generic**

**Problem**: Catching generic exceptions
```python
try:
    chunks = await retrieval_client.retrieve(...)
except Exception as e:  # Too broad!
    logger.error(f"Internal search failed: {e}")
    return f"Internal search error: {str(e)}"
```

**Solution**: Custom exception hierarchy
```python
# shared/clients/exceptions.py
class RetrievalError(Exception):
    """Base exception for retrieval errors."""
    pass

class RetrievalAuthError(RetrievalError):
    """Authentication failed."""
    pass

class RetrievalTimeoutError(RetrievalError):
    """Request timed out."""
    pass

class RetrievalValidationError(RetrievalError):
    """Invalid request parameters."""
    pass

class RetrievalServiceError(RetrievalError):
    """Rag-service returned an error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Service error {status_code}: {detail}")

# In retrieval_client.py
async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
    try:
        response = await client.post(...)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise RetrievalAuthError("Invalid service token") from e
        elif e.response.status_code >= 500:
            raise RetrievalServiceError(e.response.status_code, e.response.text) from e
        raise
    except httpx.TimeoutException as e:
        raise RetrievalTimeoutError(f"Request timed out after {self.timeout}s") from e

# In tools
try:
    chunks = await retrieval_client.retrieve(...)
except RetrievalAuthError:
    return "Authentication failed. Check service token configuration."
except RetrievalTimeoutError:
    return "Request timed out. The service may be overloaded."
except RetrievalServiceError as e:
    return f"Service error ({e.status_code}): {e.detail}"
```

**Effort**: 3-4 hours
**Risk**: Low

---

### 7. **Missing Retry Logic**

**Problem**: No retry on transient failures
- Network blips
- Service temporarily unavailable
- Rate limiting

**Solution**: Add retry decorator with exponential backoff
```python
# shared/utils/retry.py
from functools import wraps
import asyncio
from typing import TypeVar, Callable

T = TypeVar('T')

def async_retry(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple = (httpx.TimeoutException, httpx.ConnectError),
):
    """Retry async function with exponential backoff."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{max_attempts} after {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator

# In retrieval_client.py
@async_retry(max_attempts=3, backoff_factor=0.5)
async def _execute_request(self, request: SignedRequest) -> httpx.Response:
    """Execute HTTP request with retry logic."""
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        return await client.post(request.url, ...)
```

**Effort**: 2-3 hours
**Risk**: Low

---

## 🔵 Low Priority Issues (P3 - Future)

### 8. **No Unit Tests**

**Problem**: Only integration tests exist
- `retrieval_client.py` - no unit tests
- `internal_search_http.py` - no unit tests

**Solution**: Add comprehensive unit tests
```python
# shared/clients/tests/test_retrieval_client.py
import pytest
from unittest.mock import AsyncMock, patch
import httpx

@pytest.fixture
def mock_http_client():
    """Mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client

class TestRetrievalClient:
    """Unit tests for RetrievalClient."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        client = RetrievalClient()
        assert client.base_url == "http://rag-service:8002"
        assert client.timeout == 30.0

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = RetrievalClientConfig(base_url="https://prod:8000")
        client = RetrievalClient(config=config)
        assert client.base_url == "https://prod:8000"

    def test_build_payload(self):
        """Test payload construction."""
        client = RetrievalClient()
        payload = client._build_payload(
            query="test",
            user_id="user@example.com",
            max_chunks=5,
        )
        assert payload["query"] == "test"
        assert payload["user_id"] == "user@example.com"
        assert payload["max_chunks"] == 5
        assert "filters" not in payload  # Optional fields excluded

    def test_build_headers(self):
        """Test header construction."""
        client = RetrievalClient()
        headers = client._build_headers("user@example.com")
        assert headers["Content-Type"] == "application/json"
        assert headers["X-User-Email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_retrieve_success(self, mock_http_client):
        """Test successful retrieval."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "chunks": [{"content": "test", "similarity": 0.9}],
            "metadata": {"total_chunks": 1}
        }
        mock_http_client.post.return_value = mock_response

        client = RetrievalClient()

        # Act
        with patch("httpx.AsyncClient", return_value=mock_http_client):
            result = await client.retrieve(
                RetrievalRequest(query="test")
            )

        # Assert
        assert len(result.chunks) == 1
        assert result.chunks[0].content == "test"
        assert result.chunks[0].similarity == 0.9

    @pytest.mark.asyncio
    async def test_retrieve_auth_error(self, mock_http_client):
        """Test authentication error handling."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=AsyncMock(), response=mock_response
        )

        client = RetrievalClient()

        # Act & Assert
        with patch("httpx.AsyncClient", return_value=mock_http_client):
            with pytest.raises(RetrievalAuthError):
                await client.retrieve(RetrievalRequest(query="test"))

    @pytest.mark.asyncio
    async def test_retrieve_timeout(self, mock_http_client):
        """Test timeout handling."""
        # Arrange
        mock_http_client.post.side_effect = httpx.TimeoutException("Timeout")
        client = RetrievalClient()

        # Act & Assert
        with patch("httpx.AsyncClient", return_value=mock_http_client):
            with pytest.raises(RetrievalTimeoutError):
                await client.retrieve(RetrievalRequest(query="test"))
```

**Coverage Goals**:
- `retrieval_client.py`: 90%+ coverage
- `internal_search_http.py`: 85%+ coverage
- Focus on error paths and edge cases

**Effort**: 6-8 hours
**Risk**: Low (pure test addition)

---

### 9. **No Response Caching**

**Problem**: Repeated identical queries hit the service
```python
# Query 1: "8th Light" → hits service
# Query 2: "8th Light" (5 seconds later) → hits service again
```

**Solution**: Add LRU cache with TTL
```python
# shared/clients/cache.py
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Any

class TTLCache:
    """Simple TTL cache for retrieval responses."""

    def __init__(self, ttl_seconds: int = 300):  # 5 min default
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[Any, datetime]] = {}

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        self._cache[key] = (value, datetime.now())

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

# In retrieval_client.py
class RetrievalClient:
    def __init__(self, config: RetrievalClientConfig | None = None):
        self.config = config or RetrievalClientConfig()
        self.cache = TTLCache(ttl_seconds=300) if config.enable_cache else None

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        # Build cache key from request
        cache_key = self._build_cache_key(request)

        # Check cache
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit: {cache_key}")
                return cached

        # Execute request
        response = await self._execute_request(request)

        # Cache response
        if self.cache:
            self.cache.set(cache_key, response)

        return response

    def _build_cache_key(self, request: RetrievalRequest) -> str:
        """Build cache key from request parameters."""
        import hashlib
        import json

        # Include all relevant parameters
        key_dict = {
            "query": request.query,
            "user_id": request.user_id,
            "max_chunks": request.max_chunks,
            "filters": request.filters,
        }
        key_str = json.dumps(key_dict, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
```

**Benefits**:
- Reduced API calls
- Faster responses
- Lower service load

**Effort**: 3-4 hours
**Risk**: Low

---

### 10. **No Observability Metrics**

**Problem**: Can't measure performance
- No request duration metrics
- No error rate tracking
- No cache hit rate

**Solution**: Add Prometheus metrics
```python
# shared/clients/metrics.py
from prometheus_client import Counter, Histogram

retrieval_requests_total = Counter(
    'retrieval_requests_total',
    'Total retrieval requests',
    ['status', 'user_id']
)

retrieval_duration_seconds = Histogram(
    'retrieval_duration_seconds',
    'Retrieval request duration',
    ['status']
)

retrieval_chunks_returned = Histogram(
    'retrieval_chunks_returned',
    'Number of chunks returned',
    buckets=[0, 1, 5, 10, 20, 50]
)

# In retrieval_client.py
async def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
    start_time = time.time()
    status = "success"

    try:
        response = await self._execute_request(request)
        retrieval_chunks_returned.observe(len(response.chunks))
        return response
    except Exception as e:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        retrieval_duration_seconds.labels(status=status).observe(duration)
        retrieval_requests_total.labels(
            status=status,
            user_id=request.user_id
        ).inc()
```

**Effort**: 2-3 hours
**Risk**: Low

---

## Implementation Plan

### Phase 1: Critical Fixes (Week 1)
**Goal**: Eliminate code duplication

1. ✅ Create `shared/clients/retrieval_client.py`
2. ✅ Create `shared/tools/internal_search_http.py`
3. ✅ Update imports in agent-service
4. ✅ Update imports in custom_agents/profiler
5. ✅ Delete duplicated files
6. ✅ Run tests to verify nothing broke
7. ✅ Commit: "refactor: Move retrieval client to shared module"

**Deliverable**: Single source of truth (802 → 401 lines)

---

### Phase 2: Method Refactoring (Week 2)
**Goal**: Improve code readability

1. ✅ Extract `_build_payload()` from `retrieve()`
2. ✅ Extract `_build_headers()` from `retrieve()`
3. ✅ Extract `_sign_request()` from `retrieve()`
4. ✅ Extract `_execute_request()` from `retrieve()`
5. ✅ Extract `_parse_response()` from `retrieve()`
6. ✅ Extract formatters in `InternalSearchToolHTTP`
7. ✅ Run tests to verify behavior unchanged
8. ✅ Commit: "refactor: Extract smaller methods for clarity"

**Deliverable**: Methods < 15 lines each

---

### Phase 3: Type Safety (Week 3)
**Goal**: Add Pydantic models

1. ✅ Create `shared/clients/models.py`
2. ✅ Define `RetrievalRequest` model
3. ✅ Define `Chunk` model
4. ✅ Define `RetrievalResponse` model
5. ✅ Update `retrieve()` signature
6. ✅ Update tool to use models
7. ✅ Run tests to verify validation works
8. ✅ Commit: "feat: Add Pydantic models for type safety"

**Deliverable**: Type-safe API boundaries

---

### Phase 4: Error Handling (Week 4)
**Goal**: Better error messages

1. ✅ Create `shared/clients/exceptions.py`
2. ✅ Define exception hierarchy
3. ✅ Update client to raise specific exceptions
4. ✅ Update tools to catch specific exceptions
5. ✅ Add user-friendly error messages
6. ✅ Run tests to verify error handling
7. ✅ Commit: "feat: Add custom exception hierarchy"

**Deliverable**: Clear error messages for debugging

---

### Phase 5: Configuration (Week 5)
**Goal**: Remove magic strings

1. ✅ Create `shared/clients/config.py`
2. ✅ Define `RetrievalClientConfig` dataclass
3. ✅ Update client to use config
4. ✅ Update tools to use config
5. ✅ Run tests to verify defaults work
6. ✅ Commit: "refactor: Extract configuration class"

**Deliverable**: Configurable, documented defaults

---

### Phase 6: Testing (Week 6)
**Goal**: 90%+ test coverage

1. ✅ Create `shared/clients/tests/test_retrieval_client.py`
2. ✅ Add unit tests for each method
3. ✅ Add error handling tests
4. ✅ Add integration tests
5. ✅ Verify 90%+ coverage
6. ✅ Commit: "test: Add comprehensive unit tests for retrieval client"

**Deliverable**: High confidence in client behavior

---

### Phase 7: Advanced Features (Optional)
**Goal**: Production hardening

1. Retry logic (P2)
2. Response caching (P3)
3. Observability metrics (P3)

---

## Success Metrics

### Code Quality
- **Duplication**: 802 lines → 401 lines (-50%)
- **Method Size**: Max 50 lines → Max 15 lines (-70%)
- **Test Coverage**: 0% → 90%+ (unit tests)

### Maintainability
- **Single Source of Truth**: ✅ Shared module
- **Type Safety**: ✅ Pydantic models
- **Error Handling**: ✅ Custom exceptions
- **Configuration**: ✅ Centralized config

### Developer Experience
- **Import Consistency**: Same import path everywhere
- **IDE Support**: Full autocomplete with types
- **Error Messages**: Clear, actionable error text
- **Documentation**: Inline docstrings + this plan

---

## Risk Assessment

| Phase | Risk | Mitigation |
|-------|------|------------|
| Phase 1 | Import breakage | Test suite, gradual rollout |
| Phase 2 | Behavior change | Unit tests, no logic changes |
| Phase 3 | API contract change | Backward compatible models |
| Phase 4 | Exception bubbling | Try/catch at boundaries |
| Phase 5 | Config complexity | Sensible defaults |
| Phase 6 | Test maintenance | Focus on public API |

---

## Questions for Discussion

1. **Should we move to shared/ now or wait for more duplication?**
   - Recommendation: Move now (802 lines is significant)

2. **Should Phase 3 (Pydantic models) break API compatibility?**
   - Recommendation: Keep backward compatibility with dict fallback

3. **Should retry logic be opt-in or default?**
   - Recommendation: Default with circuit breaker for cascading failures

4. **Should we add caching in Phase 7 or earlier?**
   - Recommendation: Later (P3) - not critical, adds complexity

5. **Should we add integration tests or just unit tests?**
   - Recommendation: Both (integration tests already exist, add unit tests)

# API Testing Strategy - Protecting Against Breaking Changes

This document outlines our comprehensive testing strategy to protect against API changes that could break the dashboard, integrations, or user experience.

## 🚨 Problem Statement

APIs and integrations can break in several ways:
- **Dashboard Breakage**: Backend API changes break frontend expectations
- **External API Changes**: Third-party APIs (Slack, OpenAI, etc.) change contracts
- **Integration Failures**: Vector databases, monitoring services change interfaces
- **Silent Failures**: Changes that don't throw errors but break functionality

## 🛡️ Protection Strategy

### 1. **API Contract Tests**
**Location**: `bot/tests/test_api_contracts.py`, `tasks/tests/test_api_contracts.py`

**Purpose**: Ensure our API endpoints maintain expected contracts for dashboard/frontend

```python
# Example: Health endpoint contract
def test_health_endpoint_contract(self):
    response = client.get('/api/health')
    data = response.json()

    # Verify required fields dashboard expects
    required_fields = ["status", "timestamp", "uptime_seconds", "version"]
    for field in required_fields:
        assert field in data
```

**Protects Against**:
- Backend changes that break dashboard/frontend
- API response format changes
- Missing required fields
- Type changes (string → int, etc.)

### 2. **External API Integration Tests**
**Location**: `bot/tests/test_external_api_integration.py`

**Purpose**: Catch breaking changes in external APIs before they break production

```python
# Example: Slack API contract validation
def test_slack_message_api_contract(self):
    # Verify Slack API response has expected structure
    expected_response = {
        "ok": True,
        "channel": "C123",
        "ts": "1234567890.123456",
        "message": {"text": "test", "user": "U123"}
    }
    # Test our code handles this format correctly
```

**Protects Against**:
- Slack API changes breaking message sending
- OpenAI API changes breaking LLM responses
- Langfuse API changes breaking observability
- Vector database API changes breaking RAG

### 3. **Schema Validation Tests**
**Location**: Throughout test files

**Purpose**: Validate data structures match expectations

```python
# Example: Pagination schema validation
def test_pagination_contract(self):
    response = client.get('/api/task-runs?page=1')
    data = response.json()

    # Dashboard expects this exact structure
    assert "runs" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
```

**Protects Against**:
- Pagination breaking in dashboard
- Search result format changes
- Filter parameter changes

## 🎯 Testing Categories

### A. **Critical Path Protection**

**Health & Monitoring APIs**:
```bash
# These tests prevent dashboard outages
/api/health              ✅ Contract tested
/api/metrics            ✅ Contract tested
/api/services/health    ✅ Contract tested
```

**Task Management APIs**:
```bash
# These tests prevent scheduler UI breakage
/api/jobs               ✅ Contract tested
/api/scheduler/info     ✅ Contract tested
/api/task-runs         ✅ Contract tested
```

**External Integrations**:
```bash
# These tests prevent integration failures
Slack API              ✅ Contract tested
OpenAI API             ✅ Contract tested
Langfuse API           ✅ Contract tested
Elasticsearch API      ✅ Contract tested
```

### B. **Data Format Protection**

**Request Validation**:
- Job creation payloads
- User import formats
- Metrics ingestion data
- Configuration schemas

**Response Validation**:
- Pagination structures
- Error message formats
- Status field enums
- Timestamp formats

### C. **Error Handling Protection**

**Consistent Error Formats**:
```python
# All APIs should return errors in same format
{
    "error": "error_code",
    "message": "Human readable message",
    "status_code": 400
}
```

**Rate Limiting**:
```python
# Consistent rate limit responses
{
    "error": "rate_limit_exceeded",
    "retry_after": 60,
    "limit": 1000
}
```

## 🔄 Running the Tests

### Development (Fast Feedback)
```bash
# Run API contract tests only
pytest bot/tests/test_api_contracts.py -v
pytest tasks/tests/test_api_contracts.py -v

# Run external API integration tests
pytest bot/tests/test_external_api_integration.py -v
```

### CI/CD Pipeline (Comprehensive)
```bash
# Full API testing suite
pytest bot/tests/test_*api*.py tasks/tests/test_*api*.py -v

# With coverage for API endpoints
pytest --cov=bot/health --cov=tasks/app bot/tests/test_*api*.py -v
```

### Production Validation (Staging)
```bash
# Run against staging environment
ENVIRONMENT=staging pytest bot/tests/test_external_api_integration.py -v -k "not mock"
```

## 📊 Monitoring API Changes

### 1. **Version Detection**
All API responses include version headers:
```python
X-API-Version: v1
X-App-Version: 2.1.0
```

### 2. **Deprecation Warnings**
Deprecated endpoints return warnings:
```python
X-Deprecated: true
X-Sunset-Date: 2024-06-01T00:00:00Z
X-Replacement-Endpoint: /api/v2/new-endpoint
```

### 3. **Schema Evolution**
- Backward compatible field additions
- Required field validation
- Type consistency checks
- Enum value validation

## 🚀 Best Practices

### When Adding New APIs:
1. **Write contract tests first** (TDD approach)
2. **Define expected request/response formats**
3. **Test error scenarios**
4. **Include pagination/filtering if applicable**
5. **Add to API documentation**

### When Modifying Existing APIs:
1. **Run existing contract tests** to ensure no breakage
2. **Update tests for new fields** (additive changes)
3. **Maintain backward compatibility** for required fields
4. **Add deprecation warnings** for removed fields
5. **Version breaking changes** properly

### For External API Integration:
1. **Mock the expected response format** in tests
2. **Test against sandbox/staging** environments when available
3. **Monitor API provider changelogs** and release notes
4. **Implement circuit breakers** for critical integrations
5. **Have fallback strategies** for API failures

## 📈 Success Metrics

### Protection Coverage:
- ✅ **100% of public API endpoints** have contract tests
- ✅ **All external integrations** have format validation tests
- ✅ **Critical user journeys** are protected by integration tests
- ✅ **Error scenarios** are tested and return consistent formats

### Early Detection:
- 🎯 **API contract violations** caught in CI before deployment
- 🎯 **External API changes** detected in staging environment
- 🎯 **Dashboard breakage** prevented by response format validation
- 🎯 **Integration failures** caught before reaching production

## 🔧 Maintenance

### Regular Tasks:
- **Weekly**: Review external API provider changelogs
- **Monthly**: Run integration tests against live staging APIs
- **Quarterly**: Update test assertions based on API evolution
- **On deployment**: Validate all contract tests pass

### When Tests Fail:
1. **Don't ignore failing tests** - they're catching real issues
2. **Investigate the root cause** - API change vs. test issue
3. **Update code first, then tests** - maintain the contract
4. **Document breaking changes** in changelog
5. **Communicate impact** to stakeholders

This comprehensive testing strategy ensures that API changes are caught early, reducing production incidents and improving system reliability.

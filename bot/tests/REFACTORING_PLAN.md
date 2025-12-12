# Test Quality Improvement Plan

**Current Status:** Tests exist but are too permissive and poorly named.
**Goal:** Refactor to production-quality, domain-driven tests.

---

## 🔴 Current Problems

### 1. **Smoke Tests, Not Behavior Tests**
```python
# ❌ Current: Test passes even when endpoint doesn't exist
if response.status_code == 404:
    print("⚠️  WARNING: Not found")
    return  # Test passes anyway!
```

**Problem:** These are "does endpoint exist?" tests, not "does feature work?" tests.

### 2. **Names Focus on Implementation, Not Behavior**
```python
# ❌ Current: Technical implementation details
test_control_plane_oauth_callback()
test_webhook_users_import()
test_rag_service_chat_completion()

# ✅ Better: Business behavior
test_user_can_authenticate_with_google()
test_tasks_service_can_import_users_to_bot()
test_bot_generates_response_with_retrieved_context()
```

### 3. **Weak Assertions**
```python
# ❌ Current: Accepts any response as success
if response.status_code in [200, 401, 404, 500]:
    print("✅ PASS")
    return

# ✅ Better: Assert expected behavior
assert response.status_code == 200, f"Expected 200, got {response.status_code}"
data = response.json()
assert "user_id" in data, "Response missing user_id"
assert data["user_id"] == expected_user_id
```

### 4. **Mixed Concerns in Single Test**
```python
# ❌ Current: Tests multiple things
async def test_group_complete_lifecycle():
    # Creates group
    # Adds user
    # Assigns agent
    # Deletes group
    # Too much in one test!
```

---

## ✅ Refactoring Strategy

### Phase 1: Add Strict Assertions (Priority: HIGH)

Convert smoke tests to behavior tests:

```python
# BEFORE: Smoke test
@pytest.mark.integration
async def test_control_plane_oauth_callback(http_client, service_urls):
    response = await http_client.get(url, params=params)

    if response.status_code in [200, 302, 400, 401, 404]:
        print("✅ PASS: Endpoint responded")
    # Everything passes!

# AFTER: Behavior test
@pytest.mark.integration
async def test_oauth_callback_redirects_authenticated_user_to_dashboard(
    http_client, service_urls, valid_oauth_code
):
    """
    Given a valid OAuth authorization code from provider
    When user completes OAuth callback
    Then they are redirected to dashboard with valid session
    """
    # Arrange
    callback_url = f"{service_urls['control_plane']}/auth/callback"
    params = {"code": valid_oauth_code, "state": "test_state"}

    # Act
    response = await http_client.get(callback_url, params=params)

    # Assert
    assert response.status_code == 302, "Should redirect after auth"

    redirect_location = response.headers.get("location")
    assert redirect_location == "/dashboard", f"Expected dashboard redirect, got {redirect_location}"

    session_cookie = response.cookies.get("session")
    assert session_cookie is not None, "Should set session cookie"
    assert len(session_cookie) > 0, "Session cookie should not be empty"
```

### Phase 2: Rename Tests to Business Language (Priority: HIGH)

Use domain-driven naming:

```python
# Authentication Domain
test_user_can_login_with_google_oauth()
test_user_can_logout_and_session_is_invalidated()
test_unauthenticated_user_cannot_access_protected_resources()
test_user_with_expired_token_is_redirected_to_login()

# Permission Management Domain
test_admin_can_grant_agent_permission_to_user()
test_admin_can_revoke_agent_permission_from_user()
test_user_without_permission_cannot_invoke_restricted_agent()
test_user_inherits_permissions_from_group_membership()

# Job Scheduling Domain
test_admin_can_create_scheduled_ingestion_job()
test_scheduled_job_executes_at_configured_time()
test_job_can_be_paused_and_resumed()
test_failed_job_can_be_retried_manually()
test_job_execution_history_is_preserved()

# Group Management Domain
test_admin_can_create_group_with_members()
test_admin_can_assign_agent_to_group()
test_group_members_inherit_agent_permissions()
test_deleting_group_removes_all_permissions()
```

### Phase 3: Organize by Domain (Priority: MEDIUM)

Restructure test files by business domain, not service:

```
tests/
├── domains/
│   ├── authentication/
│   │   ├── test_oauth_login.py
│   │   ├── test_session_management.py
│   │   └── test_token_validation.py
│   │
│   ├── authorization/
│   │   ├── test_user_permissions.py
│   │   ├── test_group_permissions.py
│   │   └── test_rbac.py
│   │
│   ├── job_scheduling/
│   │   ├── test_job_creation.py
│   │   ├── test_job_execution.py
│   │   └── test_job_lifecycle.py
│   │
│   ├── agent_invocation/
│   │   ├── test_agent_discovery.py
│   │   ├── test_agent_execution.py
│   │   └── test_streaming_responses.py
│   │
│   └── conversation/
│       ├── test_rag_retrieval.py
│       ├── test_context_preservation.py
│       └── test_citations.py
```

### Phase 4: Add Fixtures for Test Data (Priority: MEDIUM)

Use fixtures for reusable test data:

```python
# conftest.py
@pytest.fixture
def authenticated_user(http_client, service_urls):
    """Returns a logged-in user session."""
    # Login and return session token
    pass

@pytest.fixture
def admin_user(http_client, service_urls):
    """Returns an admin user session."""
    pass

@pytest.fixture
def test_group_with_members(http_client, service_urls, admin_user):
    """Creates a test group with 3 members."""
    # Create group
    # Add members
    # Return group data
    # Cleanup after test
    pass

# Usage
async def test_group_member_can_invoke_assigned_agent(
    http_client,
    service_urls,
    test_group_with_members,
    authenticated_user
):
    # Test uses pre-created group
    pass
```

### Phase 5: Add Negative Test Cases (Priority: MEDIUM)

Test failure scenarios explicitly:

```python
# Positive test
async def test_user_with_permission_can_invoke_agent():
    # Grant permission
    # Invoke agent
    # Assert success

# Negative test
async def test_user_without_permission_cannot_invoke_agent():
    # DO NOT grant permission
    # Attempt to invoke agent
    # Assert 403 Forbidden
    # Assert error message is clear
```

---

## 📋 Concrete Refactoring Checklist

### Authentication Tests (`test_integration_authentication.py`)

- [ ] Rename tests to business behavior (e.g., `test_user_can_login_with_google_oauth`)
- [ ] Add strict assertions for redirect URLs
- [ ] Add assertions for session cookies
- [ ] Add negative tests (invalid OAuth code, expired token)
- [ ] Add fixtures for OAuth test data
- [ ] Remove "print and pass" pattern
- [ ] Use AAA pattern (Arrange, Act, Assert)

### Group Management Tests (`test_integration_groups.py`)

- [ ] Rename to business behavior (e.g., `test_admin_can_create_group`)
- [ ] Split lifecycle test into separate tests
- [ ] Add assertions for response data structure
- [ ] Add negative tests (non-admin tries to create group)
- [ ] Add fixtures for test groups
- [ ] Test permission inheritance from groups

### Job Scheduling Tests (`test_integration_extended.py`)

- [ ] Rename to business behavior (e.g., `test_scheduler_executes_job_on_schedule`)
- [ ] Add assertions for job state transitions
- [ ] Add assertions for execution history
- [ ] Add negative tests (invalid schedule format)
- [ ] Add fixtures for test jobs
- [ ] Test concurrent job execution

### Agent Tests (`test_integration_agent_lifecycle.py`)

- [ ] Rename to business behavior (e.g., `test_user_can_discover_available_agents`)
- [ ] Add assertions for agent metadata structure
- [ ] Add streaming response validation
- [ ] Add negative tests (invoke disabled agent)
- [ ] Add fixtures for test agents

### UI Tests (`test_integration_ui_endpoints.py`)

- [ ] These are actually OK as-is (smoke tests for UI are appropriate)
- [ ] But could add assertions for specific HTML elements
- [ ] Could add tests for error pages (404, 500)

---

## 🎯 Example: Before & After

### BEFORE (Current)
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_group_add_user(http_client, service_urls):
    """Test: POST /api/groups/{group_name}/users - Add user to group."""
    url = f"{service_urls['control_plane']}/api/groups/test_group/users"
    payload = {"user_id": "U12345TEST", "role": "member"}

    try:
        response = await http_client.post(url, json=payload)

        if response.status_code in [200, 201]:
            print("✅ PASS: User added to group")
        elif response.status_code == 401:
            print("✅ PASS: Auth required (401)")
        elif response.status_code == 403:
            print("✅ PASS: Admin rights required (403)")
        elif response.status_code == 404:
            print("✅ PASS: Group not found (404)")
        else:
            print(f"✅ PASS: Responded ({response.status_code})")

    except httpx.RequestError as e:
        print(f"✅ PASS: Tested - {type(e).__name__}")
```

**Problems:**
- Test "passes" regardless of outcome
- Doesn't validate actual behavior
- No cleanup
- No verification user was actually added

### AFTER (Better)
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_add_user_to_group_and_user_inherits_permissions(
    http_client,
    service_urls,
    admin_session,
    test_user,
    test_group,
):
    """
    Given an admin user and an existing group
    When admin adds user to the group
    Then user is successfully added
    And user inherits group's agent permissions
    """
    # Arrange
    add_user_url = f"{service_urls['control_plane']}/api/groups/{test_group['name']}/users"
    headers = {"Authorization": f"Bearer {admin_session['token']}"}
    payload = {"user_id": test_user["id"], "role": "member"}

    # Act
    response = await http_client.post(add_user_url, json=payload, headers=headers)

    # Assert - User added successfully
    assert response.status_code == 201, (
        f"Failed to add user to group: {response.status_code} - {response.text}"
    )

    response_data = response.json()
    assert response_data["user_id"] == test_user["id"], "Wrong user ID in response"
    assert response_data["role"] == "member", "Wrong role assigned"

    # Assert - User is in group members list
    members_url = f"{service_urls['control_plane']}/api/groups/{test_group['name']}/users"
    members_response = await http_client.get(members_url, headers=headers)

    assert members_response.status_code == 200
    members = members_response.json()["users"]

    user_ids = [m["user_id"] for m in members]
    assert test_user["id"] in user_ids, "User not found in group members list"

    # Assert - User inherits group permissions
    user_permissions_url = f"{service_urls['control_plane']}/api/users/{test_user['id']}/permissions"
    permissions_response = await http_client.get(user_permissions_url, headers=headers)

    assert permissions_response.status_code == 200
    permissions = permissions_response.json()["permissions"]

    # Group has research_agent permission, user should inherit it
    agent_names = [p["agent_name"] for p in permissions]
    assert "research_agent" in agent_names, "User did not inherit group's agent permission"
```

**Improvements:**
- ✅ Clear business behavior in name
- ✅ Given-When-Then structure in docstring
- ✅ Strong assertions that fail clearly
- ✅ Tests actual behavior (permission inheritance)
- ✅ Uses fixtures for test data
- ✅ AAA pattern (Arrange, Act, Assert)
- ✅ Descriptive failure messages

---

## 🎯 Priority Order

1. **HIGH:** Add strict assertions (stop tests passing when they shouldn't)
2. **HIGH:** Rename tests to business behavior
3. **MEDIUM:** Add fixtures for test data
4. **MEDIUM:** Add negative test cases
5. **MEDIUM:** Reorganize by domain
6. **LOW:** Add performance benchmarks

---

## 📊 Expected Outcomes

### Before Refactoring:
- ❌ Tests pass even when features broken
- ❌ Hard to understand what's being tested
- ❌ Doesn't catch bugs
- ❌ False sense of security

### After Refactoring:
- ✅ Tests fail when behavior is wrong
- ✅ Clear business intent in test names
- ✅ Catches real bugs
- ✅ Confidence in production deployments
- ✅ Living documentation of features

---

## 🚀 Next Steps

1. **Pick one domain** (e.g., authentication)
2. **Refactor 3-5 tests** using the "AFTER" pattern above
3. **Review with team** - Does this test name make sense to non-developers?
4. **Apply pattern** to remaining tests
5. **Add negative tests** for each positive test

---

**The goal isn't 100% coverage. The goal is confidence that the system works correctly.**

Current tests give **coverage metrics** (good for dashboards).
Refactored tests give **behavior validation** (good for production).

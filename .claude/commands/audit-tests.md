# Audit Test Quality

Perform a comprehensive audit of test quality patterns across all services, focusing on builders, factories, fixtures, and avoiding setup duplication.

## Objective

Ensure all tests follow best practices for maintainability:
- **Builders** with fluent `a().b()` syntax for complex object construction
- **Factories** for creating common test data
- **Fixtures** to avoid setup duplication
- **3As Pattern** (Arrange-Act-Assert) for clarity
- **DRY Principle** to minimize repeated setup code

## Process

### 1. Discovery Phase

Scan all test files and identify patterns:

```bash
# Find all test files
find bot/tests tasks/tests control_plane/tests agent-service/tests -name "test_*.py" -type f | sort

# Search for existing builders
grep -r "class.*Builder" */tests/ --include="*.py"

# Search for existing factories
grep -r "def.*_factory\|@factory\|Factory(.*)" */tests/ --include="*.py"

# Count fixture definitions
grep -r "@pytest.fixture" */tests/ --include="*.py" | wc -l

# Find conftest.py files (shared fixtures)
find */tests -name "conftest.py"
```

### 2. Pattern Analysis Phase

For each service, analyze test patterns:

#### 2.1 Builder Pattern Detection

**Good Example:**
```python
# test_builders.py or conftest.py
class JobBuilder:
    """Fluent builder for Job objects in tests."""

    def __init__(self):
        self._job_type = "default"
        self._parameters = {}
        self._schedule = None
        self._enabled = True

    def with_type(self, job_type: str) -> "JobBuilder":
        self._job_type = job_type
        return self

    def with_parameters(self, **params) -> "JobBuilder":
        self._parameters = params
        return self

    def scheduled_daily(self) -> "JobBuilder":
        self._schedule = "0 0 * * *"
        return self

    def disabled(self) -> "JobBuilder":
        self._enabled = False
        return self

    def build(self) -> dict:
        return {
            "job_type": self._job_type,
            "parameters": self._parameters,
            "schedule": self._schedule,
            "enabled": self._enabled,
        }

# Usage in tests
def test_job_creation():
    job = JobBuilder().with_type("youtube").scheduled_daily().build()
    assert job["job_type"] == "youtube"
```

**Anti-Pattern (Duplication):**
```python
def test_job_creation_1():
    job = {
        "job_type": "youtube",
        "parameters": {"channel": "test"},
        "schedule": "0 0 * * *",
        "enabled": True,
    }
    # test logic...

def test_job_creation_2():
    job = {
        "job_type": "youtube",  # Duplicated!
        "parameters": {"channel": "test2"},
        "schedule": "0 0 * * *",  # Duplicated!
        "enabled": True,
    }
    # test logic...
```

#### 2.2 Factory Pattern Detection

**Good Example:**
```python
# conftest.py
@pytest.fixture
def user_factory():
    """Factory for creating test users."""
    def _create_user(
        email: str = "test@example.com",
        is_admin: bool = False,
        is_active: bool = True,
        **kwargs
    ) -> User:
        return User(
            id=str(uuid.uuid4()),
            email=email,
            is_admin=is_admin,
            is_active=is_active,
            created_at=datetime.now(UTC),
            **kwargs
        )
    return _create_user

# Usage in tests
def test_user_permissions(user_factory):
    admin = user_factory(is_admin=True)
    regular = user_factory(email="user@example.com")
    assert admin.is_admin
    assert not regular.is_admin
```

**Anti-Pattern (Duplication):**
```python
def test_admin_user():
    admin = User(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        is_admin=True,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    # test logic...

def test_regular_user():
    user = User(  # Duplicated setup!
        id=str(uuid.uuid4()),
        email="user@example.com",
        is_admin=False,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    # test logic...
```

#### 2.3 Fixture Organization Detection

**Good Example:**
```python
# conftest.py - Shared fixtures
@pytest.fixture
def db_session():
    """Provides database session for tests."""
    session = create_test_session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def authenticated_client(db_session):
    """Client with authenticated session."""
    client = TestClient(app)
    # Setup authentication
    return client

# test_file.py - Uses shared fixtures
def test_api_endpoint(authenticated_client):
    response = authenticated_client.get("/api/jobs")
    assert response.status_code == 200
```

**Anti-Pattern (Setup Duplication):**
```python
# test_file_1.py
def test_api_endpoint_1():
    session = create_test_session()  # Duplicated!
    client = TestClient(app)
    # Setup auth...
    try:
        response = client.get("/api/jobs")
        assert response.status_code == 200
    finally:
        session.close()

# test_file_2.py
def test_api_endpoint_2():
    session = create_test_session()  # Duplicated!
    client = TestClient(app)
    # Setup auth...
    try:
        response = client.get("/api/users")
        assert response.status_code == 200
    finally:
        session.close()
```

#### 2.4 3As Pattern (Arrange-Act-Assert) Detection

**Good Example:**
```python
def test_job_scheduling():
    # Arrange
    job = JobBuilder().with_type("youtube").scheduled_daily().build()
    scheduler = SchedulerService(settings)

    # Act
    result = scheduler.add_job(job)

    # Assert
    assert result["status"] == "success"
    assert scheduler.get_job(result["job_id"]) is not None
```

**Anti-Pattern (Mixed Concerns):**
```python
def test_job_scheduling():
    job = JobBuilder().with_type("youtube").scheduled_daily().build()
    assert job["job_type"] == "youtube"  # Asserting during arrange!

    scheduler = SchedulerService(settings)
    result = scheduler.add_job(job)
    assert result["status"] == "success"

    # More arranging after acting!
    another_job = JobBuilder().with_type("gdrive").build()
    result2 = scheduler.add_job(another_job)
    assert result2["status"] == "success"
```

### 3. Identification Phase

Create a detailed analysis table for each service:

| Service | Pattern | Status | Files Affected | Duplication Score | Recommendation |
|---------|---------|--------|----------------|-------------------|----------------|
| tasks | No builders | ❌ Missing | test_api_jobs.py (15 tests) | High (80%) | Create JobBuilder |
| tasks | Factory in conftest | ✅ Good | conftest.py | Low (10%) | Keep as-is |
| bot | Builder exists | ✅ Good | test_builders.py | Low (5%) | Keep as-is |
| bot | Setup duplication | ⚠️ Warning | test_slack_service.py (20 tests) | Medium (40%) | Extract to fixture |
| control_plane | No fixtures | ❌ Missing | test_auth.py (30 tests) | High (70%) | Create conftest.py |

**Metrics to Calculate:**

1. **Duplication Score:**
   - Count repeated setup code patterns
   - `(Duplicate Lines / Total Test Lines) * 100`

2. **Builder Coverage:**
   - Objects created 5+ times → Need builder
   - Complex objects (>3 fields) → Need builder

3. **Factory Usage:**
   - Model objects → Should use factories
   - Simple DTOs → Can inline

4. **Fixture Reuse:**
   - Setup repeated 3+ times → Extract to fixture

### 4. Detailed Analysis Phase

For each anti-pattern found, document:

#### Example Finding:

**Service:** tasks
**File:** test_api_jobs.py
**Issue:** Repeated job object creation (15 occurrences)
**Duplication Score:** 75%

**Current Code Pattern:**
```python
# Repeated 15 times across different tests
job_data = {
    "job_type": "youtube_channel_ingest",
    "parameters": {
        "channel_url": "https://youtube.com/@test",
        "include_videos": True,
    },
    "schedule": "0 0 * * *",
    "enabled": True,
}
```

**Recommended Solution:**
```python
# Create in tests/builders.py or conftest.py
class JobBuilder:
    def __init__(self):
        self._job_type = "youtube_channel_ingest"
        self._parameters = {}
        self._schedule = None
        self._enabled = True

    def with_type(self, job_type: str) -> "JobBuilder":
        self._job_type = job_type
        return self

    def youtube_channel(self, url: str) -> "JobBuilder":
        self._job_type = "youtube_channel_ingest"
        self._parameters = {
            "channel_url": url,
            "include_videos": True,
        }
        return self

    def scheduled_daily(self) -> "JobBuilder":
        self._schedule = "0 0 * * *"
        return self

    def build(self) -> dict:
        return {
            "job_type": self._job_type,
            "parameters": self._parameters,
            "schedule": self._schedule,
            "enabled": self._enabled,
        }

# Usage in tests
def test_job_creation():
    job = JobBuilder().youtube_channel("https://youtube.com/@test").scheduled_daily().build()
    assert job["job_type"] == "youtube_channel_ingest"
```

**Impact:**
- Reduces test code by ~200 lines
- Makes tests more readable
- Easier to modify job structure
- Consistent test data

### 5. Proposal Phase

Present findings in priority order:

```markdown
## Proposed Test Quality Improvements

### Critical Priority (High Duplication, 50%+ repeated code)

#### 1. tasks/test_api_jobs.py - Create JobBuilder
- **Current State:** 15 tests manually create job dictionaries
- **Duplication Score:** 75%
- **Lines Duplicated:** ~200 lines
- **Impact:** High - Most frequently modified test file
- **Effort:** Medium (2-3 hours)

**Proposed Implementation:**
- Create `tasks/tests/builders.py` with JobBuilder class
- Fluent interface: `JobBuilder().youtube_channel(url).scheduled_daily().build()`
- Refactor 15 tests to use builder
- Reduces code by ~150 lines

#### 2. bot/test_slack_service.py - Extract fixtures
- **Current State:** 20 tests repeat Slack client setup
- **Duplication Score:** 60%
- **Lines Duplicated:** ~180 lines
- **Impact:** High - Brittle tests break together
- **Effort:** Low (1 hour)

**Proposed Implementation:**
- Move setup to `bot/tests/conftest.py`
- Create `@pytest.fixture` for mock_slack_client
- Parameterize for different scenarios
- Reduces code by ~140 lines

### Medium Priority (Moderate Duplication, 25-50%)

#### 3. control_plane/tests - Create user factory
- **Current State:** 12 tests manually create User objects
- **Duplication Score:** 40%
- **Lines Duplicated:** ~100 lines
- **Impact:** Medium - User creation scattered across files
- **Effort:** Low (1 hour)

**Proposed Implementation:**
```python
# control_plane/tests/conftest.py
@pytest.fixture
def user_factory():
    def _create_user(
        email: str = "test@8thlight.com",
        is_admin: bool = False,
        **kwargs
    ) -> User:
        return User(
            id=str(uuid.uuid4()),
            slack_user_id=f"U{uuid.uuid4().hex[:8]}",
            email=email,
            is_admin=is_admin,
            is_active=True,
            created_at=datetime.now(UTC),
            **kwargs
        )
    return _create_user
```

### Low Priority (Minor Improvements, <25%)

#### 4. agent-service/tests - Improve 3As separation
- **Current State:** Some tests mix arrange/act/assert
- **Duplication Score:** N/A (pattern issue, not duplication)
- **Impact:** Low - Readability concern
- **Effort:** Low (30 minutes per file)

**Proposed Improvements:**
- Add `# Arrange`, `# Act`, `# Assert` comments
- Separate concerns with blank lines
- Extract complex arranging to fixtures

### Already Good ✅

**Files following best practices:**
- ✅ bot/tests/conftest.py - Excellent fixture organization
- ✅ tasks/tests/test_youtube_audio_chunking.py - Clean 3As pattern
- ✅ agent-service/tests/test_agent_executor.py - Good use of fixtures
```

### 6. Metrics Dashboard

Create a summary report:

```markdown
## Test Quality Metrics - InsightMesh

### Overall Scores
- **Test Files Audited:** 168
- **Total Test Lines:** ~25,000
- **Duplicated Lines:** ~3,500 (14%)
- **Builders Found:** 2
- **Factories Found:** 8
- **Shared Fixtures:** 45

### Per-Service Breakdown

| Service | Tests | Duplication | Builders | Factories | Grade |
|---------|-------|-------------|----------|-----------|-------|
| tasks | 65 | 35% | 0 | 2 | C+ |
| bot | 92 | 15% | 1 | 4 | B+ |
| control_plane | 28 | 25% | 0 | 1 | B- |
| agent-service | 29 | 10% | 1 | 1 | A- |

### Recommendations Priority

1. **Critical (Do First):**
   - tasks: Create JobBuilder (saves 150 lines)
   - bot: Extract Slack fixtures (saves 140 lines)

2. **Medium (Do Next):**
   - control_plane: Add user_factory (saves 80 lines)
   - tasks: Extract scheduler fixtures (saves 60 lines)

3. **Low (Nice to Have):**
   - Improve 3As pattern separation
   - Add builder documentation
   - Standardize factory naming

### Expected Impact

**If all recommendations implemented:**
- Reduce test code by ~430 lines (1.7%)
- Improve maintainability by ~40%
- Reduce test modification time by ~30%
- Increase test clarity for new developers
```

### 7. Implementation Guidance

For each recommendation, provide step-by-step implementation:

#### Example: Creating JobBuilder

**Step 1: Create Builder File**
```bash
touch tasks/tests/builders.py
```

**Step 2: Implement Builder Class**
```python
# tasks/tests/builders.py
"""Test data builders for tasks service."""

from datetime import datetime
from typing import Any


class JobBuilder:
    """Fluent builder for Job test data.

    Examples:
        >>> job = JobBuilder().youtube_channel("@test").scheduled_daily().build()
        >>> job = JobBuilder().with_type("gdrive").with_parameters(folder_id="123").build()
    """

    def __init__(self):
        self._job_type = "youtube_channel_ingest"
        self._parameters: dict[str, Any] = {}
        self._schedule: str | None = None
        self._enabled = True
        self._metadata: dict[str, Any] = {}

    def with_type(self, job_type: str) -> "JobBuilder":
        """Set custom job type."""
        self._job_type = job_type
        return self

    def youtube_channel(self, url: str, include_videos: bool = True) -> "JobBuilder":
        """Configure as YouTube channel ingest job."""
        self._job_type = "youtube_channel_ingest"
        self._parameters = {
            "channel_url": url,
            "include_videos": include_videos,
        }
        return self

    def gdrive_ingest(self, folder_id: str, credential_id: str = "test_cred") -> "JobBuilder":
        """Configure as Google Drive ingest job."""
        self._job_type = "google_drive_ingest"
        self._parameters = {
            "folder_id": folder_id,
            "credential_id": credential_id,
        }
        return self

    def with_parameters(self, **params) -> "JobBuilder":
        """Add custom parameters."""
        self._parameters.update(params)
        return self

    def scheduled_daily(self, hour: int = 0) -> "JobBuilder":
        """Schedule for daily execution."""
        self._schedule = f"0 {hour} * * *"
        return self

    def scheduled_hourly(self) -> "JobBuilder":
        """Schedule for hourly execution."""
        self._schedule = "0 * * * *"
        return self

    def with_schedule(self, cron: str) -> "JobBuilder":
        """Set custom cron schedule."""
        self._schedule = cron
        return self

    def disabled(self) -> "JobBuilder":
        """Mark job as disabled."""
        self._enabled = False
        return self

    def with_metadata(self, **metadata) -> "JobBuilder":
        """Add custom metadata."""
        self._metadata.update(metadata)
        return self

    def build(self) -> dict[str, Any]:
        """Build the job dictionary."""
        return {
            "job_type": self._job_type,
            "parameters": self._parameters,
            "schedule": self._schedule,
            "enabled": self._enabled,
            "metadata": self._metadata,
        }
```

**Step 3: Update conftest.py**
```python
# tasks/tests/conftest.py
import pytest
from tests.builders import JobBuilder

@pytest.fixture
def job_builder():
    """Provides JobBuilder instance for tests."""
    return JobBuilder
```

**Step 4: Refactor Tests**
```python
# Before
def test_create_youtube_job():
    job_data = {
        "job_type": "youtube_channel_ingest",
        "parameters": {
            "channel_url": "https://youtube.com/@test",
            "include_videos": True,
        },
        "schedule": "0 0 * * *",
        "enabled": True,
    }
    response = client.post("/api/jobs", json=job_data)
    assert response.status_code == 201

# After
def test_create_youtube_job(job_builder):
    job = job_builder().youtube_channel("https://youtube.com/@test").scheduled_daily().build()
    response = client.post("/api/jobs", json=job)
    assert response.status_code == 201
```

**Step 5: Verify with Tests**
```bash
cd tasks && make test-file FILE=test_api_jobs.py
```

### 8. Verification Phase

After implementing improvements:

```bash
# Check duplication reduction
cd tasks && git diff HEAD~1 tests/ | grep "^-" | wc -l  # Lines removed
cd tasks && git diff HEAD~1 tests/ | grep "^+" | wc -l  # Lines added

# Verify tests still pass
make test

# Check coverage unchanged
make test-coverage
```

### 9. Documentation Phase

Create or update test documentation:

```markdown
# tasks/tests/README.md

## Test Data Builders

We use the Builder pattern for complex test data creation:

### JobBuilder

Creates job dictionaries with fluent interface:

\`\`\`python
from tests.builders import JobBuilder

# Simple usage
job = JobBuilder().youtube_channel("@test").build()

# Complex usage
job = (
    JobBuilder()
    .youtube_channel("@channel", include_videos=True)
    .scheduled_daily(hour=3)
    .with_metadata(team="data-engineering")
    .build()
)
\`\`\`

### Available Builders
- `JobBuilder` - For job creation tests
- `UserBuilder` - For user/auth tests (future)
- `CredentialBuilder` - For OAuth credential tests (future)

## Test Factories

Factories create database model instances:

\`\`\`python
def test_user_permissions(user_factory):
    admin = user_factory(is_admin=True)
    user = user_factory(email="test@example.com")
    # ...
\`\`\`

See `conftest.py` for available factories.
```

### 10. Success Criteria

✅ All tests following 3As pattern (Arrange-Act-Assert)
✅ No setup duplication >3 occurrences
✅ Complex objects (>3 fields) use builders
✅ Model creation uses factories
✅ Shared setup in conftest.py fixtures
✅ Duplication score reduced below 15%
✅ All tests still pass
✅ Test execution time unchanged
✅ Documentation updated

## Anti-Patterns to Watch For

### 1. Over-Engineering
❌ **Don't create builders for simple objects:**
```python
# BAD - Too simple for builder
class StringBuilder:
    def with_value(self, val: str) -> "StringBuilder":
        self._value = val
        return self

    def build(self) -> str:
        return self._value

# GOOD - Just use the string
name = "test_user"
```

### 2. God Builders
❌ **Don't create one builder for everything:**
```python
# BAD - Too many responsibilities
class TestDataBuilder:
    def with_user(self): ...
    def with_job(self): ...
    def with_credential(self): ...
    def with_schedule(self): ...
    # 50+ methods...

# GOOD - Separate builders per domain
JobBuilder()
UserBuilder()
CredentialBuilder()
```

### 3. Leaky Fixtures
❌ **Don't leak state between tests:**
```python
# BAD - Mutable shared state
@pytest.fixture(scope="session")
def shared_cache():
    return {}  # Shared across all tests!

# GOOD - Fresh instance per test
@pytest.fixture
def cache():
    return {}
```

### 4. Fixture Overuse
❌ **Don't create fixtures for everything:**
```python
# BAD - Trivial fixture
@pytest.fixture
def two():
    return 2

# GOOD - Just use the value
def test_addition():
    assert 1 + 2 == 3
```

## Edge Cases

**Multiple builders for same object:**
- OK if they serve different purposes
- Example: `SimpleJobBuilder` vs `ScheduledJobBuilder`
- Name should clarify intent

**Factories vs Builders:**
- **Factories:** Create saved database objects (with side effects)
- **Builders:** Create in-memory data structures (no side effects)
- Use builders when you don't need database persistence

**Parameterized fixtures:**
```python
@pytest.fixture(params=["admin", "user", "guest"])
def user_role(request):
    return request.param

def test_permissions(user_role):
    # Runs 3 times with different roles
    assert check_permission(user_role)
```

## Example Outputs

### Before Audit:
```
Test Quality Report - tasks service
- Duplication Score: 45%
- Builders: 0
- Factories: 2
- Fixture Reuse: Low
- Grade: C
```

### After Improvements:
```
Test Quality Report - tasks service
- Duplication Score: 12%
- Builders: 3 (JobBuilder, ScheduleBuilder, ParametersBuilder)
- Factories: 5 (user_factory, credential_factory, job_factory)
- Fixture Reuse: High
- Grade: A-

Improvements:
✅ Created JobBuilder - Reduced 15 tests from 200 lines to 50 lines
✅ Extracted Slack fixtures - 20 tests now share setup
✅ Added user_factory - Consistent user creation across all tests
✅ Documented patterns in tests/README.md
```

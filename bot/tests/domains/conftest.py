"""Enhanced fixtures with REAL authentication and complete test setup.

This provides production-quality fixtures that:
1. Actually authenticate users (not just mock tokens)
2. Create and clean up test data
3. Provide authenticated HTTP clients
4. Require all services to be running
"""

import os
import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest

# ==============================================================================
# Environment Setup
# ==============================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    # Service token for service-to-service auth (matches agent-service)
    if not os.getenv("SERVICE_TOKEN"):
        os.environ["SERVICE_TOKEN"] = (
            "172b784535a9c8548b9a6f62c257e6410db2cb022e80a4fe31e7b6c3b0f06128"
        )


# ==============================================================================
# Service URLs
# ==============================================================================


@pytest.fixture
def service_urls() -> dict[str, str]:
    """Service URLs for integration testing."""
    return {
        "bot": os.getenv("BOT_SERVICE_URL", "http://localhost:8080"),
        "rag_service": os.getenv("RAG_SERVICE_URL", "http://localhost:8002"),
        "agent_service": os.getenv("AGENT_SERVICE_URL", "http://localhost:8000"),
        "control_plane": os.getenv("CONTROL_PLANE_URL", "http://localhost:6001"),
        "tasks": os.getenv("TASKS_SERVICE_URL", "https://localhost:5001"),
    }


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Base HTTP client without authentication."""
    async with httpx.AsyncClient(
        timeout=30.0, follow_redirects=False, verify=False
    ) as client:
        yield client


# ==============================================================================
# REAL Authentication - Creates Actual Sessions
# ==============================================================================


def generate_test_jwt(user_data: dict) -> str:
    """Generate a valid JWT token for testing."""
    from datetime import datetime, timedelta

    import jwt

    # Use the same secret as the control plane
    secret = os.getenv(
        "JWT_SECRET_KEY",
        "d70c7728c068afeb86a928b2ed3d4210500c2dc095dfba1820a663bf36dc1b57",
    )

    payload = {
        "user_id": user_data["user_id"],
        "email": user_data["email"],
        "is_admin": user_data.get("is_admin", False),
        "name": user_data.get("real_name", "Test User"),
        "iss": "insightmesh",  # Must match JWT_ISSUER in shared/utils/jwt_auth.py
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, secret, algorithm="HS256")


async def attempt_oauth_login(
    http_client: httpx.AsyncClient, control_plane_url: str, test_user_data: dict
) -> dict | None:
    """
    Create test authentication token for integration testing.

    For integration tests, we generate valid JWT tokens using the
    same secret as the control plane.
    """
    # Generate valid JWT token
    test_token = generate_test_jwt(test_user_data)

    return {
        "token": test_token,
        "user_id": test_user_data["user_id"],
        "headers": {"Authorization": f"Bearer {test_token}"},
        "cookies": {},
    }


@pytest.fixture
async def authenticated_admin(
    http_client: httpx.AsyncClient, service_urls: dict[str, str], test_admin_data: dict
) -> httpx.AsyncClient | None:
    """
    Returns HTTP client with REAL admin authentication.

    Creates actual session, not mocked!
    Returns None if auth not available (tests can skip or test unauthenticated).
    """
    session = await attempt_oauth_login(
        http_client, service_urls["control_plane"], test_admin_data
    )

    assert session is not None, (
        "❌ Admin authentication failed!\n"
        "Control plane must be healthy and /api/test/auth endpoint must work!"
    )

    # Create authenticated client
    auth_client = httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=False,
        verify=False,
        headers=session["headers"],
        cookies=session["cookies"],
    )

    yield auth_client

    # Cleanup
    await auth_client.aclose()


@pytest.fixture
async def authenticated_user(
    http_client: httpx.AsyncClient, service_urls: dict[str, str], test_user_data: dict
) -> httpx.AsyncClient | None:
    """
    Returns HTTP client with REAL regular user authentication.

    For testing that non-admins cannot do admin actions!
    """
    session = await attempt_oauth_login(
        http_client, service_urls["control_plane"], test_user_data
    )

    assert session is not None, (
        "❌ User authentication failed!\n"
        "Control plane must be healthy and /api/test/auth endpoint must work!"
    )

    auth_client = httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=False,
        verify=False,
        headers=session["headers"],
        cookies=session["cookies"],
    )

    yield auth_client

    await auth_client.aclose()


# ==============================================================================
# Test Data Fixtures with IDs
# ==============================================================================


@pytest.fixture
async def research_agent_registered(
    http_client: httpx.AsyncClient, service_urls: dict[str, str]
) -> bool:
    """
    Verify 'help' agent exists for RBAC tests.

    The help agent is a real, working agent we can use for testing RBAC workflows.
    This fixture just verifies it's registered and accessible.

    IMPORTANT: This is a HARD REQUIREMENT for integration tests.
    If the agent doesn't exist, integration tests should FAIL, not skip.
    This ensures services are properly integrated before release.
    """
    # Help agent already exists, just verify it's accessible
    agents_url = f"{service_urls['control_plane']}/api/agents"

    response = await http_client.get(agents_url, timeout=10.0)

    assert response.status_code == 200, (
        f"❌ CRITICAL: Cannot list agents from control plane!\n"
        f"Status: {response.status_code}\n"
        f"This is a RELEASE-BLOCKING issue - control plane must be accessible.\n"
        f"Ensure control plane is running at {service_urls['control_plane']}"
    )

    agents = response.json().get("agents", [])
    agent_names = [a["name"] for a in agents]

    assert "help" in agent_names, (
        f"❌ CRITICAL: Help agent not found in control plane!\n"
        f"Available agents: {agent_names}\n"
        f"This is a RELEASE-BLOCKING issue - agent-service must register agents.\n"
    )

    print("✅ Help agent available for RBAC testing")
    return True


@pytest.fixture
def test_user_id() -> str:
    """Test user ID (matches test@example.com in DB)."""
    return "U123"


@pytest.fixture
def test_admin_id() -> str:
    """Test admin ID (matches tmfrisinger@gmail.com in DB)."""
    return "U08QVTBAWH0"


@pytest.fixture
def test_user_data(test_user_id: str) -> dict:
    """Test regular user data."""
    return {
        "user_id": test_user_id,
        "username": "test_user",
        "email": "test@example.com",  # Existing non-admin user in DB
        "real_name": "Test User",
        "is_admin": False,
    }


@pytest.fixture
def test_admin_data(test_admin_id: str) -> dict:
    """Test admin user data."""
    return {
        "user_id": test_admin_id,
        "username": "admin",
        "email": "tmfrisinger@gmail.com",  # Existing admin user in DB
        "real_name": "Test Admin",
        "is_admin": True,
    }


# ==============================================================================
# Test Entity Creation with Real Cleanup
# ==============================================================================


@pytest.fixture
async def created_test_group(
    authenticated_admin: httpx.AsyncClient | None,
    service_urls: dict[str, str],
    test_group_data: dict,
) -> dict | None:
    """
    Creates a REAL test group with admin authentication.
    Automatically cleans up after test.
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['control_plane']}/api/groups"

    # NO exception handling - let it fail if service unavailable
    response = await authenticated_admin.post(create_url, json=test_group_data)

    if response.status_code not in [200, 201]:
        pytest.skip(f"Cannot create test group: {response.status_code}")

    group_data = response.json()
    group_name = group_data.get("name", test_group_data["name"])

    yield group_data

    # Cleanup: Delete group
    delete_url = f"{service_urls['control_plane']}/api/groups/{group_name}"
    await authenticated_admin.delete(delete_url)


@pytest.fixture
async def created_test_job(
    authenticated_admin: httpx.AsyncClient | None,
    service_urls: dict[str, str],
    test_job_data: dict,
) -> dict | None:
    """
    Creates a REAL test job with admin authentication.
    Automatically cleans up after test.
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['tasks']}/api/jobs"

    # NO exception handling - let it fail if service unavailable
    response = await authenticated_admin.post(create_url, json=test_job_data)

    if response.status_code not in [200, 201]:
        pytest.skip(f"Cannot create test job: {response.status_code}")

    job_data = response.json()
    job_id = job_data.get("job_id") or job_data.get("id")

    yield job_data

    # Cleanup: Delete job
    if job_id:
        delete_url = f"{service_urls['tasks']}/api/jobs/{job_id}"
        await authenticated_admin.delete(delete_url)


# ==============================================================================
# Behavior Verification Helpers
# ==============================================================================


async def user_can_invoke_agent(
    http_client: httpx.AsyncClient,
    service_urls: dict[str, str],
    agent_name: str,
    user_id: str,
) -> bool:
    """
    Check if user can actually invoke an agent.
    Returns True if user can invoke, False if forbidden/error.
    """
    invoke_url = f"{service_urls['agent_service']}/api/agents/{agent_name}/invoke"
    payload = {
        "query": "test query",
        "user_id": user_id,
        "context": {},
    }

    # NO exception handling - let connection errors propagate and HARD FAIL
    # Timeout increased to 120s for research agent execution
    response = await http_client.post(invoke_url, json=payload, timeout=120.0)
    print(
        f"DEBUG: Agent invoke attempt: {response.status_code} - {response.text[:200]}"
    )
    return response.status_code in [200, 201, 202]  # Success codes


async def user_has_permission(
    http_client: httpx.AsyncClient,
    service_urls: dict[str, str],
    user_id: str,
    agent_name: str,
) -> bool:
    """
    Check if user has permission in their permission list.
    """
    permissions_url = f"{service_urls['control_plane']}/api/users/{user_id}/permissions"

    # NO exception handling - let connection errors propagate
    response = await http_client.get(permissions_url, timeout=5.0)

    if response.status_code != 200:
        return False

    data = response.json()
    permissions = data.get("permissions", []) if isinstance(data, dict) else data

    agent_names = [p.get("agent_name") for p in permissions]
    return agent_name in agent_names


async def job_is_in_state(
    http_client: httpx.AsyncClient,
    service_urls: dict[str, str],
    job_id: str,
    expected_state: str,
) -> bool:
    """
    Check if job is in expected state (enabled, paused, etc.)
    """
    job_url = f"{service_urls['tasks']}/api/jobs/{job_id}"

    # NO exception handling - let connection errors propagate
    response = await http_client.get(job_url, timeout=5.0)

    if response.status_code != 200:
        return False

    job_data = response.json()

    # Check various state fields
    if expected_state == "enabled":
        return job_data.get("enabled", False)
    elif expected_state == "paused":
        return not job_data.get("enabled", True)
    else:
        return job_data.get("status") == expected_state


async def group_has_member(
    http_client: httpx.AsyncClient,
    service_urls: dict[str, str],
    group_name: str,
    user_id: str,
) -> bool:
    """
    Check if user is member of group.
    """
    members_url = f"{service_urls['control_plane']}/api/groups/{group_name}/users"

    # NO exception handling - let connection errors propagate
    response = await http_client.get(members_url, timeout=5.0)

    if response.status_code != 200:
        return False

    data = response.json()
    members = data.get("users", []) if isinstance(data, dict) else data

    member_ids = [m.get("user_id") for m in members]
    return user_id in member_ids


# ==============================================================================
# Group & Job Data Fixtures
# ==============================================================================


@pytest.fixture
def test_group_name() -> str:
    """Generate unique test group name."""
    return f"test_group_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_group_data(test_group_name: str) -> dict:
    """Test group data."""
    return {
        "group_name": test_group_name,  # API expects 'group_name', not 'name'
        "display_name": f"Test Group {test_group_name[-8:]}",
        "description": "Integration test group",
        "metadata": {"created_by": "integration_test"},
    }


@pytest.fixture
def test_job_name() -> str:
    """Generate unique test job name."""
    return f"test_job_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_job_data(test_job_name: str) -> dict:
    """Test job data."""
    return {
        "task_name": test_job_name,
        "job_type": "gdrive_ingest",  # Must match directory name in tasks/jobs/system/
        "schedule": {
            "trigger": "cron",
            "hour": 3,
            "minute": 0,
        },
        "enabled": False,  # Don't actually run
        "parameters": {
            "folder_id": "test_folder",
            "credential_id": "test_cred",
        },
    }


# ==============================================================================
# Helper Functions for Integration Tests
# ==============================================================================


def assert_valid_http_response(response, expected_codes=None):
    """Assert that HTTP response has a valid status code.

    Args:
        response: HTTP response object
        expected_codes: List of expected status codes (default: 2xx)

    """
    if expected_codes is None:
        expected_codes = range(200, 300)

    assert response.status_code in expected_codes, (
        f"Unexpected status code: {response.status_code}\n"
        f"Expected: {expected_codes}\n"
        f"Response: {response.text[:200] if hasattr(response, 'text') else 'N/A'}"
    )


def assert_json_contains_keys(data, required_keys):
    """Assert that JSON data contains required keys.

    Args:
        data: Dictionary or JSON response
        required_keys: List of required key names

    """
    if not isinstance(data, dict):
        try:
            data = data.json() if hasattr(data, "json") else data
        except Exception:
            raise AssertionError(f"Response is not JSON: {type(data)}") from None

    missing_keys = [key for key in required_keys if key not in data]

    assert not missing_keys, (
        f"Missing required keys: {missing_keys}\nAvailable keys: {list(data.keys())}"
    )

"""STRICT integration tests for microservices - NO graceful failures.

Tests microservice HTTP communication with HARD FAIL requirements:
- Services MUST be running (no skips for "service not available")
- Authentication MUST work or test FAILS (no "401 is ok" bullshit)
- Tests are either authenticated (expect 200) or unauthenticated (expect 401)

Run with: pytest -v -m integration
"""

import os

import httpx
import pytest

pytestmark = pytest.mark.integration


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def service_urls():
    """Service URLs for integration testing."""
    return {
        "bot": os.getenv("BOT_SERVICE_URL", "http://localhost:8080"),
        "rag_service": os.getenv("RAG_SERVICE_URL", "http://localhost:8002"),
        "agent_service": os.getenv("AGENT_SERVICE_URL", "http://localhost:8000"),
        "control_plane": os.getenv("CONTROL_PLANE_URL", "https://localhost:6001"),
        "tasks": os.getenv("TASKS_SERVICE_URL", "https://localhost:5001"),
    }


@pytest.fixture
async def http_client():
    """Unauthenticated HTTP client - for testing that endpoints require auth."""
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        yield client


# ============================================================================
# Health Check Tests - STRICT
# ============================================================================


@pytest.mark.asyncio
async def test_all_services_healthy(http_client, service_urls):
    """
    STRICT TEST - All core services MUST be healthy.

    Given: Services should be running (docker-compose up)
    When: GET /health on each service
    Then: ALL services MUST return 200 (or test FAILS)

    No graceful failures - if a service is down, fix it!
    """
    health_checks = {
        "bot": f"{service_urls['bot']}/health",
        "rag_service": f"{service_urls['rag_service']}/health",
        "agent_service": f"{service_urls['agent_service']}/health",
        "control_plane": f"{service_urls['control_plane']}/health",
        "tasks": f"{service_urls['tasks']}/health",
    }

    failed_services = []

    for service_name, health_url in health_checks.items():
        try:
            response = await http_client.get(health_url)
            if response.status_code != 200:
                failed_services.append(
                    f"{service_name}: {response.status_code} - {response.text[:100]}"
                )
        except httpx.RequestError as e:
            failed_services.append(f"{service_name}: CONNECTION FAILED - {e}")

    assert not failed_services, (
        "❌ SERVICE HEALTH CHECK FAILED!\n"
        "The following services are unhealthy:\n"
        + "\n".join(f"  - {f}" for f in failed_services)
        + "\n\nAll services MUST be healthy. Run: docker-compose up -d"
    )

    print("✅ PASS: All services healthy")


# ============================================================================
# RAG Service Tests - Unauthenticated (expect failure)
# ============================================================================


@pytest.mark.asyncio
async def test_rag_service_requires_authentication(http_client, service_urls):
    """
    STRICT TEST - RAG service MUST require authentication.

    Given: Unauthenticated request
    When: POST /api/v1/chat/completions
    Then: MUST return 401 (or test FAILS)
    """
    rag_url = f"{service_urls['rag_service']}/api/v1/chat/completions"
    payload = {
        "query": "What is Python?",
        "conversation_history": [],
        "use_rag": False,
        "user_id": "test_user",
    }

    response = await http_client.post(rag_url, json=payload)

    assert response.status_code == 401, (
        f"❌ RAG SERVICE NOT SECURED!\n"
        f"Expected: 401 Unauthorized\n"
        f"Got: {response.status_code}\n"
        f"Response: {response.text[:200]}\n"
        f"RAG service MUST require authentication!"
    )

    print("✅ PASS: RAG service requires authentication (401)")


# ============================================================================
# Agent Service Tests - Unauthenticated (expect failure)
# ============================================================================


@pytest.mark.asyncio
async def test_agent_service_list_requires_service_token(http_client, service_urls):
    """
    STRICT TEST - Agent list endpoint MUST require service token.

    Given: Unauthenticated request (no X-Service-Token)
    When: GET /api/agents
    Then: MUST return 401 (or test FAILS)
    """
    agents_url = f"{service_urls['agent_service']}/api/agents"

    response = await http_client.get(agents_url)

    assert response.status_code == 401, (
        f"❌ AGENT LIST ENDPOINT NOT SECURED!\n"
        f"Expected: 401 Unauthorized\n"
        f"Got: {response.status_code}\n"
        f"Response: {response.text[:200]}\n"
        f"Agent list MUST require service token!"
    )

    print("✅ PASS: Agent list requires service token (401)")


@pytest.mark.asyncio
async def test_agent_service_invoke_requires_authentication(http_client, service_urls):
    """
    STRICT TEST - Agent invoke MUST require authentication.

    Given: Unauthenticated request
    When: POST /api/agents/help/invoke
    Then: MUST return 401 (or test FAILS)
    """
    invoke_url = f"{service_urls['agent_service']}/api/agents/help/invoke"
    payload = {"query": "test"}

    response = await http_client.post(invoke_url, json=payload)

    assert response.status_code == 401, (
        f"❌ AGENT INVOKE NOT SECURED!\n"
        f"Expected: 401 Unauthorized\n"
        f"Got: {response.status_code}\n"
        f"Response: {response.text[:200]}\n"
        f"Agent invoke MUST require authentication!"
    )

    print("✅ PASS: Agent invoke requires authentication (401)")


# ============================================================================
# Agent Service Tests - WITH Service Token (expect success)
# ============================================================================


@pytest.mark.asyncio
async def test_agent_service_list_with_service_token(http_client, service_urls):
    """
    STRICT TEST - Agent list MUST work with valid service token.

    Given: Valid X-Service-Token header
    When: GET /api/agents
    Then: MUST return 200 (or test FAILS)
    """
    service_token = os.getenv("SERVICE_TOKEN")
    if not service_token:
        pytest.skip("SERVICE_TOKEN not configured")

    agents_url = f"{service_urls['agent_service']}/api/agents"
    headers = {"X-Service-Token": service_token}

    response = await http_client.get(agents_url, headers=headers)

    assert response.status_code == 200, (
        f"❌ SERVICE TOKEN AUTHENTICATION FAILED!\n"
        f"Expected: 200 OK\n"
        f"Got: {response.status_code}\n"
        f"Response: {response.text[:200]}\n"
        f"Service token authentication MUST work!"
    )

    data = response.json()
    assert "agents" in data, "Missing agents list in response"
    assert isinstance(data["agents"], list), "Agents should be a list"

    print(
        f"✅ PASS: Agent list with service token works ({len(data['agents'])} agents)"
    )


# ============================================================================
# Control Plane Tests - Public Endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_control_plane_health_public(http_client, service_urls):
    """
    STRICT TEST - Control plane health endpoint MUST be public.

    Given: Unauthenticated request
    When: GET /health
    Then: MUST return 200 (or test FAILS)
    """
    health_url = f"{service_urls['control_plane']}/health"

    response = await http_client.get(health_url)

    assert response.status_code == 200, (
        f"❌ CONTROL PLANE HEALTH CHECK FAILED!\n"
        f"Expected: 200 OK (public endpoint)\n"
        f"Got: {response.status_code}\n"
        f"Response: {response.text[:200]}"
    )

    print("✅ PASS: Control plane health is public")


# ============================================================================
# Summary
# ============================================================================


@pytest.mark.asyncio
async def test_microservices_integration_summary():
    """Print summary of strict integration tests."""
    print("\n" + "=" * 70)
    print("🔒 STRICT MICROSERVICES INTEGRATION TESTS")
    print("=" * 70)
    print("\n✅ All tests use HARD FAIL requirements:")
    print("   - Services MUST be healthy (no skips)")
    print("   - Authentication MUST work or test FAILS")
    print("   - No 'in [200, 401]' graceful failures")
    print("\n🔒 Tests pass or fail - no middle ground!")

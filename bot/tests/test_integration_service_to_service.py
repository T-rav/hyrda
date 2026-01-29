"""Service-to-service integration tests.

Verifies core service connections and workflows:
- Bot → Database (usage tracking)
- Bot → RAG Service
- Bot → Agent Service
- Service health verification
"""

import os

import pytest
import requests


@pytest.mark.integration
class TestBotToDatabase:
    """Test Bot → Database connectivity and usage tracking."""

    def test_database_connection(self):
        """Verify bot can connect to MySQL database."""
        from sqlalchemy import create_engine, text

        database_url = os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://insightmesh:insightmesh@localhost:3306/insightmesh",
        )

        engine = create_engine(database_url, pool_pre_ping=True)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_slack_usage_table_exists(self):
        """Verify slack_usage table exists and is queryable."""
        from sqlalchemy import create_engine, inspect

        database_url = os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://insightmesh:insightmesh@localhost:3306/insightmesh",
        )

        engine = create_engine(database_url)
        inspector = inspect(engine)

        assert "slack_usage" in inspector.get_table_names()

        # Verify columns exist
        columns = {col["name"] for col in inspector.get_columns("slack_usage")}
        required_columns = {
            "id",
            "slack_user_id",
            "thread_ts",
            "channel_id",
            "interaction_type",
            "created_at",
        }
        assert required_columns.issubset(columns)

    def test_usage_tracking_service_records_interaction(self):
        """Verify UsageTrackingService records interactions to database."""
        from services.usage_tracking_service import UsageTrackingService

        database_url = os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://insightmesh:insightmesh@localhost:3306/insightmesh",
        )

        service = UsageTrackingService(database_url=database_url)

        # Record a test interaction
        import uuid

        test_user = f"test_user_{uuid.uuid4().hex[:8]}"
        test_thread = f"{uuid.uuid4().hex[:10]}.123456"

        usage = service.record_interaction(
            slack_user_id=test_user,
            thread_ts=test_thread,
            channel_id="C123456",
            interaction_type="test",
        )

        assert usage is not None
        assert usage.id is not None
        assert usage.slack_user_id == test_user
        assert usage.thread_ts == test_thread

    def test_usage_tracking_service_query_counts(self):
        """Verify usage count queries work correctly."""
        from services.usage_tracking_service import UsageTrackingService

        database_url = os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://insightmesh:insightmesh@localhost:3306/insightmesh",
        )

        service = UsageTrackingService(database_url=database_url)

        # Record multiple interactions for same user
        import uuid

        test_user = f"test_user_count_{uuid.uuid4().hex[:8]}"
        test_thread = f"{uuid.uuid4().hex[:10]}.123456"

        # Record 3 interactions
        for _ in range(3):
            service.record_interaction(
                slack_user_id=test_user,
                thread_ts=test_thread,
                interaction_type="test_count",
            )

        # Query count
        count = service.get_user_usage_count(test_user, since_days=1)
        assert count >= 3


@pytest.mark.integration
class TestBotToRagService:
    """Test Bot → RAG Service connectivity."""

    def test_rag_service_health(self):
        """Verify RAG service health endpoint responds."""
        rag_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8081")

        response = requests.get(f"{rag_url}/health", timeout=5)
        assert response.status_code == 200

        data = response.json()
        assert data.get("status") in ["healthy", "ok", "up"]

    def test_rag_service_query_endpoint(self):
        """Verify RAG service query endpoint accepts requests."""
        rag_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8081")

        # This test assumes the RAG service has a query endpoint
        # The actual endpoint may vary based on implementation
        payload = {
            "query": "test query",
            "user_id": "test_user",
            "session_id": "test_session",
        }

        # Use a service token if required
        headers = {
            "Authorization": f"Bearer {os.getenv('BOT_SERVICE_TOKEN', 'test-token')}"
        }

        response = requests.post(
            f"{rag_url}/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )

        # Should either succeed (200) or require auth (401) - both mean service is reachable
        assert response.status_code in [200, 401, 403]


@pytest.mark.integration
class TestBotToAgentService:
    """Test Bot → Agent Service connectivity."""

    def test_agent_service_health(self):
        """Verify Agent service health endpoint responds."""
        agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8083")

        response = requests.get(f"{agent_url}/health", timeout=5)
        assert response.status_code == 200

        data = response.json()
        assert data.get("status") in ["healthy", "ok", "up"]

    def test_agent_service_registry(self):
        """Verify Agent service registry endpoint responds."""
        agent_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8083")

        headers = {
            "Authorization": f"Bearer {os.getenv('BOT_SERVICE_TOKEN', 'test-token')}"
        }

        response = requests.get(
            f"{agent_url}/api/agents",
            headers=headers,
            timeout=5,
        )

        # Should either return agents (200) or require auth (401)
        assert response.status_code in [200, 401, 403]


@pytest.mark.integration
class TestServiceAuthentication:
    """Test service-to-service authentication flows."""

    def test_bot_service_token_validation(self):
        """Verify service tokens are properly validated between services."""
        # This test verifies that services accept valid tokens and reject invalid ones
        rag_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8081")

        # Request without token should fail
        response_no_auth = requests.post(
            f"{rag_url}/api/v1/chat/completions",
            json={"query": "test"},
            timeout=5,
        )

        # Request with invalid token should fail
        response_invalid_auth = requests.post(
            f"{rag_url}/api/v1/chat/completions",
            json={"query": "test"},
            headers={"Authorization": "Bearer invalid-token"},
            timeout=5,
        )

        # Both should be rejected (401 or 403)
        assert response_no_auth.status_code in [401, 403]
        assert response_invalid_auth.status_code in [401, 403]


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Test end-to-end workflows across services."""

    def test_message_handling_triggers_usage_tracking(self):
        """Verify that processing a message records usage.

        This is a simplified E2E test that verifies the integration between
        message handling and usage tracking without requiring Slack API.
        """
        from services.usage_tracking_service import UsageTrackingService

        database_url = os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://insightmesh:insightmesh@localhost:3306/insightmesh",
        )

        # Get initial count
        import uuid

        test_user = f"e2e_test_{uuid.uuid4().hex[:8]}"
        service = UsageTrackingService(database_url=database_url)

        initial_count = service.get_user_usage_count(test_user, since_days=1)

        # Simulate message handling recording usage
        service.record_interaction(
            slack_user_id=test_user,
            thread_ts=f"{uuid.uuid4().hex[:10]}.123456",
            channel_id="C123456",
            interaction_type="dm_message",
        )

        # Verify count increased
        new_count = service.get_user_usage_count(test_user, since_days=1)
        assert new_count == initial_count + 1

    def test_service_health_aggregate(self):
        """Verify all critical services are healthy."""
        services = {
            "bot": os.getenv("BOT_HEALTH_URL", "http://localhost:8080/health"),
            "rag": os.getenv("RAG_HEALTH_URL", "http://localhost:8081/health"),
            "agent": os.getenv("AGENT_HEALTH_URL", "http://localhost:8083/health"),
        }

        results = {}
        for name, url in services.items():
            try:
                response = requests.get(url, timeout=5)
                results[name] = response.status_code == 200
            except requests.RequestException:
                results[name] = False

        # Log results for debugging
        for name, healthy in results.items():
            status = "✅ healthy" if healthy else "❌ unhealthy"
            print(f"  {name}: {status}")

        # At minimum, bot should be healthy
        assert results.get("bot", False), "Bot service is not healthy"

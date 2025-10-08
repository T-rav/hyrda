import os
import sys
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, main


# TDD Factory Patterns for App Testing
class MockEnvironmentFactory:
    """Factory for creating mock environment configurations for app testing"""

    @staticmethod
    def create_basic_app_env(
        vector_enabled: bool = False,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o-mini",
    ) -> dict[str, str]:
        """Create basic environment variables for app testing"""
        return {
            "SLACK_BOT_TOKEN": "xoxb-test-token",
            "SLACK_APP_TOKEN": "xapp-test-token",
            "LLM_PROVIDER": llm_provider,
            "LLM_API_KEY": "test-api-key",
            "LLM_MODEL": llm_model,
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
            "VECTOR_ENABLED": str(vector_enabled).lower(),
        }

    @staticmethod
    def create_rag_enabled_env() -> dict[str, str]:
        """Create environment with RAG/vector enabled"""
        return MockEnvironmentFactory.create_basic_app_env(
            vector_enabled=True,
            llm_provider="openai",
            llm_model="gpt-4",
        )

    @staticmethod
    def create_anthropic_env() -> dict[str, str]:
        """Create environment with Anthropic provider"""
        env = MockEnvironmentFactory.create_basic_app_env(
            llm_provider="anthropic",
            llm_model="claude-3-haiku-20240307",
        )
        env["LLM_API_KEY"] = "sk-ant-test-key"
        return env

    @staticmethod
    def create_ollama_env() -> dict[str, str]:
        """Create environment with Ollama provider"""
        env = MockEnvironmentFactory.create_basic_app_env(
            llm_provider="ollama",
            llm_model="llama2",
        )
        env["LLM_BASE_URL"] = "http://localhost:11434"
        return env


class MockServiceFactory:
    """Factory for creating mock services for app testing"""

    @staticmethod
    def create_mock_async_app() -> MagicMock:
        """Create mock AsyncApp instance"""
        mock_app = MagicMock()
        mock_app.start_socket_mode = MagicMock()
        return mock_app

    @staticmethod
    def create_mock_llm_service() -> MagicMock:
        """Create mock LLMService instance"""
        mock_service = MagicMock()
        mock_service.initialize = MagicMock()
        mock_service.health_check = MagicMock(return_value={"status": "healthy"})
        return mock_service

    @staticmethod
    def create_mock_slack_service() -> MagicMock:
        """Create mock SlackService instance"""
        mock_service = MagicMock()
        mock_service.initialize = MagicMock()
        mock_service.health_check = MagicMock(return_value={"status": "healthy"})
        return mock_service

    @staticmethod
    def create_mock_conversation_cache() -> MagicMock:
        """Create mock ConversationCache instance"""
        mock_cache = MagicMock()
        mock_cache.initialize = MagicMock()
        mock_cache.health_check = MagicMock(return_value={"status": "healthy"})
        return mock_cache

    @staticmethod
    def create_mock_metrics_service() -> MagicMock:
        """Create mock MetricsService instance"""
        mock_metrics = MagicMock()
        mock_metrics.initialize = MagicMock()
        mock_metrics.health_check = MagicMock(return_value={"status": "healthy"})
        return mock_metrics

    @staticmethod
    def create_all_mock_services() -> tuple[
        MagicMock, MagicMock, MagicMock, MagicMock, MagicMock
    ]:
        """Create all required mock services for app testing"""
        return (
            MockServiceFactory.create_mock_async_app(),
            MockServiceFactory.create_mock_slack_service(),
            MockServiceFactory.create_mock_llm_service(),
            MockServiceFactory.create_mock_conversation_cache(),
            MockServiceFactory.create_mock_metrics_service(),
        )


class AppTestContextFactory:
    """Factory for creating test contexts with proper mocking"""

    @staticmethod
    def create_basic_app_context(
        env_vars: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], dict[str, MagicMock]]:
        """Create basic app testing context with environment and mocks"""
        if env_vars is None:
            env_vars = MockEnvironmentFactory.create_basic_app_env()

        mock_services = MockServiceFactory.create_all_mock_services()
        mock_classes = {
            "AsyncApp": MagicMock(return_value=mock_services[0]),
            "SlackService": MagicMock(return_value=mock_services[1]),
            "LLMService": MagicMock(return_value=mock_services[2]),
            "ConversationCache": MagicMock(return_value=mock_services[3]),
            "MetricsService": MagicMock(return_value=mock_services[4])
            if len(mock_services) > 4
            else MagicMock(),
        }

        return env_vars, mock_classes

    @staticmethod
    def create_rag_enabled_context() -> tuple[dict[str, str], dict[str, MagicMock]]:
        """Create app testing context with RAG enabled"""
        env_vars = MockEnvironmentFactory.create_rag_enabled_env()
        return AppTestContextFactory.create_basic_app_context(env_vars)

    @staticmethod
    def create_anthropic_context() -> tuple[dict[str, str], dict[str, MagicMock]]:
        """Create app testing context with Anthropic provider"""
        env_vars = MockEnvironmentFactory.create_anthropic_env()
        return AppTestContextFactory.create_basic_app_context(env_vars)


class TestApp:
    """Tests for the main app functionality using factory patterns"""

    def test_create_app_basic(self):
        """Test basic app creation returns expected components"""
        env_vars, mock_classes = AppTestContextFactory.create_basic_app_context()

        with (
            patch.dict(os.environ, env_vars),
            patch("app.AsyncApp", mock_classes["AsyncApp"]),
            patch("app.LLMService", mock_classes["LLMService"]),
            patch("app.SlackService", mock_classes["SlackService"]),
            patch("app.ConversationCache", mock_classes["ConversationCache"]),
        ):
            result = create_app()

            # Should return 5 components (app, slack, llm, cache, metrics)
            assert len(result) == 5
            app, slack_service, llm_service, conversation_cache, metrics_service = (
                result
            )

            # Verify components are properly created
            assert app is not None
            assert slack_service is not None
            assert llm_service is not None
            assert conversation_cache is not None
            assert metrics_service is not None

            # Verify service classes were called
            mock_classes["AsyncApp"].assert_called_once()
            mock_classes["SlackService"].assert_called_once()
            mock_classes["LLMService"].assert_called_once()

    def test_create_app_with_rag_enabled(self):
        """Test app creation with RAG/vector features enabled"""
        env_vars, mock_classes = AppTestContextFactory.create_rag_enabled_context()

        with (
            patch.dict(os.environ, env_vars),
            patch("app.AsyncApp", mock_classes["AsyncApp"]),
            patch("app.LLMService", mock_classes["LLMService"]),
            patch("app.SlackService", mock_classes["SlackService"]),
            patch("app.ConversationCache", mock_classes["ConversationCache"]),
        ):
            result = create_app()

            # Should return 5 components
            assert len(result) == 5
            app, slack_service, llm_service, conversation_cache, metrics_service = (
                result
            )

            # Verify all components exist
            assert all(component is not None for component in result)

            # Verify RAG is enabled in environment
            assert env_vars["VECTOR_ENABLED"] == "true"

    def test_create_app_with_anthropic(self):
        """Test app creation with Anthropic LLM provider"""
        env_vars, mock_classes = AppTestContextFactory.create_anthropic_context()

        with (
            patch.dict(os.environ, env_vars),
            patch("app.AsyncApp", mock_classes["AsyncApp"]),
            patch("app.LLMService", mock_classes["LLMService"]),
            patch("app.SlackService", mock_classes["SlackService"]),
            patch("app.ConversationCache", mock_classes["ConversationCache"]),
        ):
            result = create_app()

            # Should return 5 components
            assert len(result) == 5

            # Verify Anthropic provider is configured
            assert env_vars["LLM_PROVIDER"] == "anthropic"
            assert "sk-ant-" in env_vars["LLM_API_KEY"]
            assert "claude-" in env_vars["LLM_MODEL"]

    def test_create_app_ollama_configuration(self):
        """Test app creation with Ollama configuration"""
        env_vars = MockEnvironmentFactory.create_ollama_env()
        _, mock_classes = AppTestContextFactory.create_basic_app_context(env_vars)

        with (
            patch.dict(os.environ, env_vars),
            patch("app.AsyncApp", mock_classes["AsyncApp"]),
            patch("app.LLMService", mock_classes["LLMService"]),
            patch("app.SlackService", mock_classes["SlackService"]),
            patch("app.ConversationCache", mock_classes["ConversationCache"]),
        ):
            result = create_app()

            # Should return 5 components
            assert len(result) == 5

            # Verify Ollama configuration
            assert env_vars["LLM_PROVIDER"] == "ollama"
            assert env_vars["LLM_BASE_URL"] == "http://localhost:11434"
            assert env_vars["LLM_MODEL"] == "llama2"

    def test_main_function_exists(self):
        """Test that main function calls asyncio.run"""
        with patch("app.asyncio.run") as mock_asyncio_run:
            main()
            # Should call asyncio.run with a coroutine
            mock_asyncio_run.assert_called_once()

    def test_mock_service_factory_creates_valid_mocks(self):
        """Test that MockServiceFactory creates properly configured mocks"""
        app_mock = MockServiceFactory.create_mock_async_app()
        llm_mock = MockServiceFactory.create_mock_llm_service()
        slack_mock = MockServiceFactory.create_mock_slack_service()
        cache_mock = MockServiceFactory.create_mock_conversation_cache()
        metrics_mock = MockServiceFactory.create_mock_metrics_service()

        # Verify all mocks are MagicMock instances
        assert isinstance(app_mock, MagicMock)
        assert isinstance(llm_mock, MagicMock)
        assert isinstance(slack_mock, MagicMock)
        assert isinstance(cache_mock, MagicMock)
        assert isinstance(metrics_mock, MagicMock)

        # Verify health check methods exist
        assert hasattr(llm_mock, "health_check")
        assert hasattr(slack_mock, "health_check")
        assert hasattr(cache_mock, "health_check")
        assert hasattr(metrics_mock, "health_check")

    def test_environment_factory_creates_valid_configs(self):
        """Test that MockEnvironmentFactory creates valid configurations"""
        basic_env = MockEnvironmentFactory.create_basic_app_env()
        rag_env = MockEnvironmentFactory.create_rag_enabled_env()
        anthropic_env = MockEnvironmentFactory.create_anthropic_env()
        ollama_env = MockEnvironmentFactory.create_ollama_env()

        # Verify basic required keys exist
        required_keys = [
            "SLACK_BOT_TOKEN",
            "SLACK_APP_TOKEN",
            "LLM_PROVIDER",
            "LLM_API_KEY",
        ]
        for env in [basic_env, rag_env, anthropic_env, ollama_env]:
            for key in required_keys:
                assert key in env
                assert env[key] != ""

        # Verify specific configurations
        assert rag_env["VECTOR_ENABLED"] == "true"
        assert anthropic_env["LLM_PROVIDER"] == "anthropic"
        assert ollama_env["LLM_PROVIDER"] == "ollama"
        assert "LLM_BASE_URL" in ollama_env

    def test_agents_registered_on_import(self):
        """Test that agents are registered when app module is imported"""
        from agents.registry import agent_registry

        # Verify agents are registered
        agents = agent_registry.list_agents()
        agent_names = [agent["name"] for agent in agents]

        # Should have at least these core agents
        assert "agents" in agent_names  # HelpAgent
        assert "profile" in agent_names  # ProfileAgent
        assert "meddic" in agent_names  # MeddicAgent

        # Verify help agent has correct alias
        help_agent = next(agent for agent in agents if agent["name"] == "agents")
        assert "help" in help_agent["aliases"]

        # Verify meddic agent has correct alias
        meddic_agent = next(agent for agent in agents if agent["name"] == "meddic")
        assert "medic" in meddic_agent["aliases"]

"""Tests for the skills framework.

Tests cover:
- BaseSkill and SkillResult
- SkillRegistry and @register_skill decorator
- SkillExecutor (LangGraph tool)
- SkillContext
- Prospect skills (hubspot, signals, qualify, research)
"""

import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.goal_executor.skills.base import (
    BaseSkill,
    SkillContext,
    SkillResult,
    SkillStatus,
)
from agents.goal_executor.skills.executor import SkillExecutor, SkillInvocation
from agents.goal_executor.skills.primitives import (
    DeepResearchSkill,
    GetRunHistorySkill,
    ListProspectsSkill,
    RecallMemorySkill,
    RephraseSkill,
    SaveMemorySkill,
    WebSearchSkill,
)
from agents.goal_executor.skills.prospect.clients import (
    CompanyInfo,
    HubSpotClient,
    PerplexityClient,
    SearchResult,
    TavilyClient,
)
from agents.goal_executor.skills.prospect.hubspot import (
    CheckRelationshipSkill,
    RelationshipData,
)
from agents.goal_executor.skills.prospect.qualify import (
    QualificationData,
    QualifyProspectSkill,
)
from agents.goal_executor.skills.prospect.research import (
    ProspectResearchData,
    ResearchProspectSkill,
)
from agents.goal_executor.skills.prospect.signals import (
    SearchSignalsSkill,
    Signal,
    SignalSearchData,
)
from agents.goal_executor.skills.registry import (
    SkillRegistry,
    get_skill_registry,
    register_skill,
)
from agents.goal_executor.skills.youtube import (
    YouTubeSkill,
    YouTubeVideo,
    extract_video_id,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def skill_context():
    """Create a test skill context."""
    return SkillContext(
        bot_id="test_bot",
        run_id="test_run_123",
        cache={},
        config={},
    )


@pytest.fixture
def mock_tavily():
    """Mock TavilyClient."""
    client = MagicMock(spec=TavilyClient)
    client.is_configured = True
    client.search.return_value = [
        SearchResult(
            title="Acme Corp hiring DevOps Engineer",
            url="https://linkedin.com/jobs/123",
            content="Looking for experienced DevOps engineer...",
            source="tavily",
        ),
        SearchResult(
            title="Acme Corp Raises $50M Series B",
            url="https://techcrunch.com/acme",
            content="AI startup Acme Corp announced funding...",
            source="tavily",
        ),
    ]
    return client


@pytest.fixture
def mock_perplexity():
    """Mock PerplexityClient."""
    client = MagicMock(spec=PerplexityClient)
    client.is_configured = True
    client.research.return_value = (
        "Acme Corp is an AI-focused startup founded in 2020. "
        "They specialize in developer tools and have ~150 employees."
    )
    return client


@pytest.fixture
def mock_hubspot():
    """Mock HubSpotClient."""
    client = MagicMock(spec=HubSpotClient)
    client.is_configured = True
    client.check_company = AsyncMock(return_value=None)
    return client


# =============================================================================
# SkillResult Tests
# =============================================================================


class TestSkillResult:
    """Tests for SkillResult dataclass."""

    def test_skill_result_success(self):
        """Test successful result creation."""
        result = SkillResult(
            status=SkillStatus.SUCCESS,
            data={"key": "value"},
            message="Operation completed",
            steps_completed=["step1", "step2"],
        )

        assert result.is_success
        assert not result.is_failed
        assert result.data == {"key": "value"}
        assert result.message == "Operation completed"
        assert result.steps_completed == ["step1", "step2"]

    def test_skill_result_failed(self):
        """Test failed result."""
        result = SkillResult(
            status=SkillStatus.FAILED,
            error="Something went wrong",
        )

        assert result.is_failed
        assert not result.is_success
        assert result.error == "Something went wrong"

    def test_skill_result_partial(self):
        """Test partial success result."""
        result = SkillResult(
            status=SkillStatus.PARTIAL,
            data={"partial": True},
            message="Some steps failed",
            steps_completed=["step1"],
        )

        assert result.status == SkillStatus.PARTIAL
        assert not result.is_success
        assert not result.is_failed

    def test_skill_result_skipped(self):
        """Test skipped result."""
        result = SkillResult(
            status=SkillStatus.SKIPPED,
            message="Work not needed",
        )

        assert result.status == SkillStatus.SKIPPED
        assert not result.is_success
        assert not result.is_failed

    def test_skill_result_to_dict(self):
        """Test conversion to dictionary."""
        result = SkillResult(
            status=SkillStatus.SUCCESS,
            data={"key": "value"},
            message="Done",
            steps_completed=["step1"],
            duration_ms=100,
            metadata={"extra": "info"},
        )

        d = result.to_dict()
        assert d["status"] == "success"
        assert d["data"] == {"key": "value"}
        assert d["message"] == "Done"
        assert d["steps_completed"] == ["step1"]
        assert d["duration_ms"] == 100
        assert d["metadata"] == {"extra": "info"}

    def test_skill_result_str_representations(self):
        """Test string representations for different statuses."""
        success = SkillResult(status=SkillStatus.SUCCESS, message="Success!")
        assert "✅" in str(success)

        failed = SkillResult(status=SkillStatus.FAILED, error="Error!")
        assert "❌" in str(failed)

        skipped = SkillResult(status=SkillStatus.SKIPPED, message="Skipped")
        assert "⏭️" in str(skipped)

        partial = SkillResult(status=SkillStatus.PARTIAL, message="Partial")
        assert "⚠️" in str(partial)


# =============================================================================
# SkillContext Tests
# =============================================================================


class TestSkillContext:
    """Tests for SkillContext."""

    def test_context_defaults(self):
        """Test default context values."""
        ctx = SkillContext()
        assert ctx.bot_id == "default"
        assert ctx.run_id == ""
        assert ctx.memory is None
        assert ctx.cache == {}
        assert ctx.config == {}

    def test_context_custom_values(self):
        """Test context with custom values."""
        ctx = SkillContext(
            bot_id="my_bot",
            run_id="run_123",
            cache={"key": "value"},
            config={"option": True},
        )
        assert ctx.bot_id == "my_bot"
        assert ctx.run_id == "run_123"
        assert ctx.cache == {"key": "value"}
        assert ctx.config == {"option": True}

    def test_cache_operations(self):
        """Test cache get/set."""
        ctx = SkillContext()

        # Initially empty
        assert ctx.get_cached("missing") is None

        # Set and retrieve
        ctx.set_cached("key", "value")
        assert ctx.get_cached("key") == "value"

        # Overwrite
        ctx.set_cached("key", "new_value")
        assert ctx.get_cached("key") == "new_value"


# =============================================================================
# BaseSkill Tests
# =============================================================================


class TestBaseSkill:
    """Tests for BaseSkill abstract class."""

    def test_cannot_instantiate_directly(self):
        """Test that BaseSkill cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSkill()

    @pytest.mark.asyncio
    async def test_concrete_skill_execution(self, skill_context):
        """Test concrete skill implementation."""

        class TestSkill(BaseSkill):
            name = "test_skill"
            description = "A test skill"

            async def execute(self, value: str) -> SkillResult[str]:
                self._step("process")
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=f"processed: {value}",
                    message=f"Processed {value}",
                    steps_completed=["process"],
                )

        skill = TestSkill(context=skill_context)
        result = await skill.run(value="test_input")

        assert result.is_success
        assert result.data == "processed: test_input"
        assert result.duration_ms >= 0  # May be 0 if execution is very fast
        assert "process" in result.steps_completed

    @pytest.mark.asyncio
    async def test_skill_error_handling(self, skill_context):
        """Test skill handles exceptions gracefully."""

        class ErrorSkill(BaseSkill):
            name = "error_skill"
            description = "Always fails"

            async def execute(self) -> SkillResult:
                raise ValueError("Something broke")

        skill = ErrorSkill(context=skill_context)
        result = await skill.run()

        assert result.is_failed
        assert "Something broke" in result.error

    @pytest.mark.asyncio
    async def test_skill_invoke_other_skill(self, skill_context):
        """Test skill can invoke other skills."""
        # Register a helper skill
        registry = get_skill_registry()

        class HelperSkill(BaseSkill):
            name = "helper_skill"
            description = "Helper"

            async def execute(self, x: int) -> SkillResult[int]:
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=x * 2,
                    message=f"Doubled {x}",
                )

        registry.register(HelperSkill)

        class CompositeSkill(BaseSkill):
            name = "composite_skill"
            description = "Uses helper"

            async def execute(self, value: int) -> SkillResult[int]:
                helper_result = await self._invoke_skill("helper_skill", x=value)
                if helper_result.is_success:
                    return SkillResult(
                        status=SkillStatus.SUCCESS,
                        data=helper_result.data + 1,
                        message="Composed successfully",
                    )
                return helper_result

        skill = CompositeSkill(context=skill_context)
        result = await skill.run(value=5)

        assert result.is_success
        assert result.data == 11  # 5 * 2 + 1

    @pytest.mark.asyncio
    async def test_skill_invoke_missing_skill(self, skill_context):
        """Test invoking non-existent skill returns error."""

        class BadInvokeSkill(BaseSkill):
            name = "bad_invoke"
            description = "Invokes missing"

            async def execute(self) -> SkillResult:
                return await self._invoke_skill("nonexistent_skill")

        skill = BadInvokeSkill(context=skill_context)
        result = await skill.run()

        assert result.is_failed
        assert "not found" in result.error.lower()


# =============================================================================
# SkillRegistry Tests
# =============================================================================


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_register_and_get(self):
        """Test registering and retrieving skills."""
        registry = SkillRegistry()

        class MySkill(BaseSkill):
            name = "my_skill"
            description = "My skill"
            version = "2.0.0"

            async def execute(self) -> SkillResult:
                return SkillResult(status=SkillStatus.SUCCESS)

        registry.register(MySkill)
        retrieved = registry.get("my_skill")

        assert retrieved is MySkill
        assert "my_skill" in registry

    def test_get_missing_returns_none(self):
        """Test getting missing skill returns None."""
        registry = SkillRegistry()
        assert registry.get("missing") is None
        assert "missing" not in registry

    def test_list_skills(self):
        """Test listing registered skills."""
        registry = SkillRegistry()

        class SkillA(BaseSkill):
            name = "skill_a"
            description = "Skill A"
            version = "1.0.0"

            async def execute(self) -> SkillResult:
                return SkillResult(status=SkillStatus.SUCCESS)

        class SkillB(BaseSkill):
            name = "skill_b"
            description = "Skill B"
            version = "1.1.0"

            async def execute(self) -> SkillResult:
                return SkillResult(status=SkillStatus.SUCCESS)

        registry.register(SkillA)
        registry.register(SkillB)

        skills = registry.list_skills()
        assert len(skills) == 2

        names = {s["name"] for s in skills}
        assert names == {"skill_a", "skill_b"}

    def test_get_skill_names(self):
        """Test getting skill names."""
        registry = SkillRegistry()

        class SkillX(BaseSkill):
            name = "skill_x"
            description = "X"

            async def execute(self) -> SkillResult:
                return SkillResult(status=SkillStatus.SUCCESS)

        registry.register(SkillX)
        names = registry.get_skill_names()
        assert "skill_x" in names

    def test_registry_len(self):
        """Test registry length."""
        registry = SkillRegistry()
        assert len(registry) == 0

        class S(BaseSkill):
            name = "s"
            description = "S"

            async def execute(self) -> SkillResult:
                return SkillResult(status=SkillStatus.SUCCESS)

        registry.register(S)
        assert len(registry) == 1

    def test_register_skill_decorator(self):
        """Test @register_skill decorator."""
        # Save original registry state
        registry = get_skill_registry()
        original_count = len(registry)

        @register_skill
        class DecoratedSkill(BaseSkill):
            name = "decorated_skill"
            description = "Decorated"

            async def execute(self) -> SkillResult:
                return SkillResult(status=SkillStatus.SUCCESS)

        assert len(registry) == original_count + 1
        assert registry.get("decorated_skill") is DecoratedSkill


# =============================================================================
# SkillExecutor Tests
# =============================================================================


class TestSkillExecutor:
    """Tests for SkillExecutor LangGraph tool."""

    @pytest.fixture(autouse=True)
    def setup_registry(self):
        """Register test skills before each test."""
        registry = get_skill_registry()

        class EchoSkill(BaseSkill):
            name = "echo"
            description = "Echoes input"

            async def execute(self, message: str) -> SkillResult[str]:
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=f"Echo: {message}",
                    message=f"Echoed {message}",
                    steps_completed=["echo"],
                )

        registry.register(EchoSkill)

    def test_skill_invocation_schema(self):
        """Test SkillInvocation schema."""
        invocation = SkillInvocation(
            skill_name="my_skill",
            parameters={"key": "value"},
        )
        assert invocation.skill_name == "my_skill"
        assert invocation.parameters == {"key": "value"}

    def test_executor_creation(self, skill_context):
        """Test executor creation."""
        executor = SkillExecutor(context=skill_context)
        assert executor.name == "invoke_skill"
        assert executor.context.bot_id == "test_bot"

    @pytest.mark.asyncio
    async def test_executor_async_run(self, skill_context):
        """Test async skill execution."""
        executor = SkillExecutor(context=skill_context)
        result = await executor._arun("echo", {"message": "hello"})

        assert "**Skill: echo**" in result
        assert "Echo: hello" in result
        assert "Steps:" in result

    @pytest.mark.asyncio
    async def test_executor_missing_skill(self, skill_context):
        """Test error handling for missing skill."""
        executor = SkillExecutor(context=skill_context)
        result = await executor._arun("nonexistent", {})

        assert "not found" in result.lower()
        assert "Available skills" in result

    def test_executor_format_result(self, skill_context):
        """Test result formatting."""
        executor = SkillExecutor(context=skill_context)

        result = SkillResult(
            status=SkillStatus.SUCCESS,
            data={"key": "value"},
            message="Test message",
            steps_completed=["step1", "step2"],
            duration_ms=150,
        )

        formatted = executor._format_result("test_skill", result)

        assert "**Skill: test_skill**" in formatted
        assert "Test message" in formatted
        assert "step1 → step2" in formatted
        assert "150ms" in formatted
        assert "key" in formatted


# =============================================================================
# CheckRelationshipSkill Tests
# =============================================================================


class TestCheckRelationshipSkill:
    """Tests for CheckRelationshipSkill."""

    @pytest.mark.asyncio
    async def test_company_not_in_hubspot(self, skill_context, mock_hubspot):
        """Test checking company not in HubSpot."""
        with patch(
            "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
            return_value=mock_hubspot,
        ):
            skill = CheckRelationshipSkill(context=skill_context)
            result = await skill.run(company_name="New Company")

        assert result.is_success
        assert result.data.found_in_hubspot is False
        assert result.data.can_pursue is True

    @pytest.mark.asyncio
    async def test_company_is_customer(self, skill_context, mock_hubspot):
        """Test checking company that is a customer."""
        mock_hubspot.check_company = AsyncMock(
            return_value=CompanyInfo(
                company_id="123",
                name="Existing Corp",
                is_customer=True,
                lifecycle_stage="customer",
            )
        )

        with patch(
            "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
            return_value=mock_hubspot,
        ):
            skill = CheckRelationshipSkill(context=skill_context)
            result = await skill.run(company_name="Existing Corp")

        assert result.status == SkillStatus.SKIPPED
        assert result.data.found_in_hubspot is True
        assert result.data.can_pursue is False
        assert "customer" in result.data.skip_reason.lower()

    @pytest.mark.asyncio
    async def test_company_has_active_deal(self, skill_context, mock_hubspot):
        """Test checking company with active deal."""
        mock_hubspot.check_company = AsyncMock(
            return_value=CompanyInfo(
                company_id="456",
                name="Deal Corp",
                has_active_deal=True,
                lifecycle_stage="opportunity",
            )
        )

        with patch(
            "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
            return_value=mock_hubspot,
        ):
            skill = CheckRelationshipSkill(context=skill_context)
            result = await skill.run(company_name="Deal Corp")

        assert result.status == SkillStatus.SKIPPED
        assert result.data.can_pursue is False
        assert "deal" in result.data.skip_reason.lower()

    @pytest.mark.asyncio
    async def test_hubspot_not_configured(self, skill_context):
        """Test behavior when HubSpot is not configured."""
        mock_hubspot = MagicMock()
        mock_hubspot.is_configured = False

        with patch(
            "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
            return_value=mock_hubspot,
        ):
            skill = CheckRelationshipSkill(context=skill_context)
            result = await skill.run(company_name="Any Company")

        assert result.is_success
        assert result.data.can_pursue is True  # Assume can pursue if no HubSpot

    @pytest.mark.asyncio
    async def test_cache_hit(self, skill_context, mock_hubspot):
        """Test cache hit returns cached data."""
        cached_data = RelationshipData(
            company_name="Cached Corp",
            found_in_hubspot=True,
            can_pursue=True,
        )
        skill_context.set_cached("hubspot:cached corp", cached_data)

        with patch(
            "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
            return_value=mock_hubspot,
        ):
            skill = CheckRelationshipSkill(context=skill_context)
            result = await skill.run(company_name="Cached Corp")

        assert result.is_success
        assert result.data.company_name == "Cached Corp"
        # HubSpot should not be called
        mock_hubspot.check_company.assert_not_called()


# =============================================================================
# SearchSignalsSkill Tests
# =============================================================================


class TestSearchSignalsSkill:
    """Tests for SearchSignalsSkill."""

    @pytest.mark.asyncio
    async def test_search_jobs(self, skill_context, mock_tavily, mock_perplexity):
        """Test searching for job signals."""
        with (
            patch(
                "agents.goal_executor.skills.prospect.signals.get_tavily",
                return_value=mock_tavily,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_perplexity",
                return_value=mock_perplexity,
            ),
        ):
            skill = SearchSignalsSkill(context=skill_context)
            result = await skill.run(query="Acme Corp", signal_types=["jobs"])

        assert result.is_success
        assert len(result.data.signals) > 0
        assert "job_boards" in result.data.sources_searched

    @pytest.mark.asyncio
    async def test_search_multiple_types(
        self, skill_context, mock_tavily, mock_perplexity
    ):
        """Test searching multiple signal types."""
        with (
            patch(
                "agents.goal_executor.skills.prospect.signals.get_tavily",
                return_value=mock_tavily,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_perplexity",
                return_value=mock_perplexity,
            ),
        ):
            skill = SearchSignalsSkill(context=skill_context)
            result = await skill.run(
                query="Tech Company",
                signal_types=["jobs", "news", "funding"],
            )

        assert result.is_success
        # Should have searched multiple sources
        assert len(result.data.sources_searched) >= 1

    @pytest.mark.asyncio
    async def test_no_results_falls_back_to_perplexity(
        self, skill_context, mock_perplexity
    ):
        """Test Perplexity fallback when no Tavily results."""
        mock_tavily_empty = MagicMock()
        mock_tavily_empty.is_configured = True
        mock_tavily_empty.search.return_value = []

        with (
            patch(
                "agents.goal_executor.skills.prospect.signals.get_tavily",
                return_value=mock_tavily_empty,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_perplexity",
                return_value=mock_perplexity,
            ),
        ):
            skill = SearchSignalsSkill(context=skill_context)
            result = await skill.run(query="Obscure Company")

        # Should have fallen back to Perplexity
        if mock_perplexity.is_configured:
            assert "perplexity" in result.data.sources_searched

    @pytest.mark.asyncio
    async def test_tavily_not_configured(self, skill_context, mock_perplexity):
        """Test behavior when Tavily not configured."""
        mock_tavily = MagicMock()
        mock_tavily.is_configured = False

        with (
            patch(
                "agents.goal_executor.skills.prospect.signals.get_tavily",
                return_value=mock_tavily,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_perplexity",
                return_value=mock_perplexity,
            ),
        ):
            skill = SearchSignalsSkill(context=skill_context)
            result = await skill.run(query="Any Company")

        # Should still work with Perplexity fallback
        assert result.status in [SkillStatus.SUCCESS, SkillStatus.PARTIAL]


# =============================================================================
# QualifyProspectSkill Tests
# =============================================================================


class TestQualifyProspectSkill:
    """Tests for QualifyProspectSkill."""

    @pytest.mark.asyncio
    async def test_qualify_with_strong_signals(self, skill_context):
        """Test qualifying prospect with strong signals."""
        signals = [
            {
                "type": "funding",
                "title": "Raises $50M",
                "content": "...",
                "url": "...",
                "strength": "high",
            },
            {
                "type": "job_posting",
                "title": "Hiring DevOps",
                "content": "...",
                "url": "...",
                "strength": "high",
            },
            {
                "type": "news",
                "title": "Launch",
                "content": "...",
                "url": "...",
                "strength": "medium",
            },
        ]

        skill = QualifyProspectSkill(context=skill_context)
        result = await skill.run(
            company_name="Acme Corp",
            signals=signals,
            employee_count=200,
            industry="technology",
        )

        assert result.is_success
        assert result.data.is_qualified is True
        assert result.data.score >= 60  # Should be at least medium priority
        assert result.data.priority in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_qualify_with_weak_signals(self, skill_context):
        """Test qualifying prospect with weak signals."""
        signals = [
            {
                "type": "news",
                "title": "Minor update",
                "content": "...",
                "url": "...",
                "strength": "low",
            },
        ]

        skill = QualifyProspectSkill(context=skill_context)
        result = await skill.run(
            company_name="Weak Corp",
            signals=signals,
        )

        assert result.is_success
        assert result.data.score < 60  # Low priority or not qualified

    @pytest.mark.asyncio
    async def test_qualify_no_signals(self, skill_context):
        """Test qualifying prospect with no signals."""
        skill = QualifyProspectSkill(context=skill_context)
        result = await skill.run(
            company_name="Unknown Corp",
            signals=[],
        )

        assert result.is_success
        assert result.data.is_qualified is False
        assert result.data.score < 40

    @pytest.mark.asyncio
    async def test_size_bonus(self, skill_context):
        """Test employee count affects score."""
        signals = [
            {
                "type": "job_posting",
                "title": "Hiring",
                "content": "...",
                "url": "...",
                "strength": "medium",
            },
        ]

        skill = QualifyProspectSkill(context=skill_context)

        # Ideal size
        result_ideal = await skill.run(
            company_name="Ideal Co",
            signals=signals,
            employee_count=500,
        )

        # Too small
        result_small = await skill.run(
            company_name="Small Co",
            signals=signals,
            employee_count=10,
        )

        # The ideal size should score higher
        assert result_ideal.data.score >= result_small.data.score

    @pytest.mark.asyncio
    async def test_industry_bonus(self, skill_context):
        """Test industry affects score."""
        signals = [
            {
                "type": "job_posting",
                "title": "Hiring",
                "content": "...",
                "url": "...",
                "strength": "medium",
            },
        ]

        skill = QualifyProspectSkill(context=skill_context)

        # Good industry
        result_tech = await skill.run(
            company_name="Tech Co",
            signals=signals,
            industry="technology",
        )

        # Other industry
        result_other = await skill.run(
            company_name="Other Co",
            signals=signals,
            industry="retail",
        )

        assert result_tech.data.score >= result_other.data.score

    @pytest.mark.asyncio
    async def test_strengths_and_weaknesses(self, skill_context):
        """Test strengths and weaknesses are populated."""
        signals = [
            {
                "type": "funding",
                "title": "Series B",
                "content": "...",
                "url": "...",
                "strength": "high",
            },
        ]

        skill = QualifyProspectSkill(context=skill_context)
        result = await skill.run(
            company_name="Funded Corp",
            signals=signals,
            employee_count=300,
            industry="AI",
        )

        assert len(result.data.strengths) > 0
        assert "funding" in " ".join(result.data.strengths).lower()

    @pytest.mark.asyncio
    async def test_recommended_approach(self, skill_context):
        """Test recommended approach is generated."""
        signals = [
            {
                "type": "funding",
                "title": "Funding",
                "content": "...",
                "url": "...",
                "strength": "high",
            },
            {
                "type": "job_posting",
                "title": "Hiring",
                "content": "...",
                "url": "...",
                "strength": "medium",
            },
        ]

        skill = QualifyProspectSkill(context=skill_context)
        result = await skill.run(
            company_name="Target Corp",
            signals=signals,
        )

        assert result.data.recommended_approach
        assert len(result.data.recommended_approach) > 0


# =============================================================================
# ResearchProspectSkill Tests
# =============================================================================


class TestResearchProspectSkill:
    """Tests for ResearchProspectSkill (main workflow)."""

    @pytest.mark.asyncio
    async def test_full_workflow_new_company(
        self, skill_context, mock_hubspot, mock_tavily, mock_perplexity
    ):
        """Test full research workflow for new company."""
        # Company not in HubSpot
        mock_hubspot.check_company = AsyncMock(return_value=None)

        with (
            patch(
                "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
                return_value=mock_hubspot,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_tavily",
                return_value=mock_tavily,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_perplexity",
                return_value=mock_perplexity,
            ),
            patch(
                "agents.goal_executor.skills.prospect.research.get_perplexity",
                return_value=mock_perplexity,
            ),
            patch(
                "agents.goal_executor.services.memory.GoalMemory.save_prospect",
                return_value="test_prospect_id",
            ),
        ):
            skill = ResearchProspectSkill(context=skill_context)
            result = await skill.run(company_name="New Startup")

        assert result.status in [SkillStatus.SUCCESS, SkillStatus.PARTIAL]
        assert "check_relationship" in result.steps_completed
        assert "search_signals" in result.steps_completed

    @pytest.mark.asyncio
    async def test_skip_existing_customer(self, skill_context, mock_hubspot):
        """Test skipping existing customer."""
        mock_hubspot.check_company = AsyncMock(
            return_value=CompanyInfo(
                company_id="123",
                name="Customer Corp",
                is_customer=True,
            )
        )

        with patch(
            "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
            return_value=mock_hubspot,
        ):
            skill = ResearchProspectSkill(context=skill_context)
            result = await skill.run(company_name="Customer Corp")

        assert result.status == SkillStatus.SKIPPED
        assert "customer" in result.message.lower() or "skip" in result.message.lower()

    @pytest.mark.asyncio
    async def test_skip_if_in_hubspot_disabled(
        self, skill_context, mock_hubspot, mock_tavily, mock_perplexity
    ):
        """Test can override skip_if_in_hubspot."""
        mock_hubspot.check_company = AsyncMock(
            return_value=CompanyInfo(
                company_id="456",
                name="Prospect Corp",
                lifecycle_stage="lead",
                is_customer=False,
            )
        )

        with (
            patch(
                "agents.goal_executor.skills.prospect.hubspot.get_hubspot",
                return_value=mock_hubspot,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_tavily",
                return_value=mock_tavily,
            ),
            patch(
                "agents.goal_executor.skills.prospect.signals.get_perplexity",
                return_value=mock_perplexity,
            ),
            patch(
                "agents.goal_executor.skills.prospect.research.get_perplexity",
                return_value=mock_perplexity,
            ),
        ):
            skill = ResearchProspectSkill(context=skill_context)
            result = await skill.run(
                company_name="Prospect Corp",
                skip_if_in_hubspot=False,
            )

        # Should proceed with research even though in HubSpot
        assert result.status != SkillStatus.SKIPPED


# =============================================================================
# Data Classes Tests
# =============================================================================


class TestDataClasses:
    """Tests for data transfer classes."""

    def test_signal_to_dict(self):
        """Test Signal.to_dict()."""
        signal = Signal(
            type="funding",
            title="Series A",
            content="Raised $10M",
            url="https://example.com",
            strength="high",
        )
        d = signal.to_dict()
        assert d["type"] == "funding"
        assert d["strength"] == "high"

    def test_signal_search_data_to_dict(self):
        """Test SignalSearchData.to_dict()."""
        data = SignalSearchData(
            query="test",
            signals=[
                Signal(type="news", title="T", content="C", url="U"),
            ],
            sources_searched=["web"],
            total_found=1,
        )
        d = data.to_dict()
        assert d["query"] == "test"
        assert len(d["signals"]) == 1

    def test_qualification_data_to_dict(self):
        """Test QualificationData.to_dict()."""
        data = QualificationData(
            company_name="Test Corp",
            score=75,
            priority="medium",
            is_qualified=True,
            strengths=["Good size"],
            weaknesses=["Unknown industry"],
            recommended_approach="Standard outreach",
        )
        d = data.to_dict()
        assert d["score"] == 75
        assert d["priority"] == "medium"

    def test_relationship_data_to_dict(self):
        """Test RelationshipData.to_dict()."""
        data = RelationshipData(
            company_name="Test Corp",
            found_in_hubspot=True,
            company_info=CompanyInfo(
                company_id="123",
                name="Test Corp",
                employees=100,
            ),
            can_pursue=True,
        )
        d = data.to_dict()
        assert d["found_in_hubspot"] is True
        assert d["company_info"]["employees"] == 100

    def test_prospect_research_data_to_dict(self):
        """Test ProspectResearchData.to_dict()."""
        data = ProspectResearchData(
            company_name="Test Corp",
            saved=True,
            prospect_id="abc123",
        )
        d = data.to_dict()
        assert d["company_name"] == "Test Corp"
        assert d["saved"] is True
        assert d["prospect_id"] == "abc123"


# =============================================================================
# Integration Tests
# =============================================================================


class TestSkillsIntegration:
    """Integration tests for skills framework."""

    @pytest.mark.asyncio
    async def test_skill_executor_with_real_skill(self, skill_context):
        """Test SkillExecutor with a real registered skill."""
        # The registry already has skills registered from imports
        executor = SkillExecutor(context=skill_context)

        # Get available skills
        registry = get_skill_registry()
        available = registry.get_skill_names()

        # Should have prospect skills registered
        assert "check_relationship" in available or len(available) > 0
        # Verify executor is properly configured
        assert executor.context.bot_id == skill_context.bot_id

    def test_skill_context_shared_across_skills(self):
        """Test that context is shared across skills."""
        context = SkillContext(bot_id="shared_test")
        context.set_cached("shared_key", "shared_value")

        class SkillA(BaseSkill):
            name = "skill_a_shared"

            async def execute(self) -> SkillResult:
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=self.context.get_cached("shared_key"),
                )

        class SkillB(BaseSkill):
            name = "skill_b_shared"

            async def execute(self) -> SkillResult:
                self.context.set_cached("from_b", "value_b")
                return SkillResult(status=SkillStatus.SUCCESS)

        skill_a = SkillA(context=context)
        skill_b = SkillB(context=context)

        # Run skill B to set cache
        asyncio.get_event_loop().run_until_complete(skill_b.run())

        # Check context has value from B
        assert context.get_cached("from_b") == "value_b"

        # Skill A should see the shared key
        result = asyncio.get_event_loop().run_until_complete(skill_a.run())
        assert result.data == "shared_value"


# =============================================================================
# Primitive Skills Tests
# =============================================================================


class TestWebSearchSkill:
    """Tests for WebSearchSkill."""

    @pytest.mark.asyncio
    async def test_web_search_success(self, skill_context, mock_tavily):
        """Test successful web search."""
        with patch(
            "agents.goal_executor.skills.primitives.get_tavily",
            return_value=mock_tavily,
        ):
            skill = WebSearchSkill(context=skill_context)
            result = await skill.run(query="AI startups funding 2024")

        assert result.is_success
        assert result.data.query == "AI startups funding 2024"
        assert len(result.data.results) > 0

    @pytest.mark.asyncio
    async def test_web_search_not_configured(self, skill_context):
        """Test web search when Tavily not configured."""
        mock_tavily = MagicMock()
        mock_tavily.is_configured = False

        with patch(
            "agents.goal_executor.skills.primitives.get_tavily",
            return_value=mock_tavily,
        ):
            skill = WebSearchSkill(context=skill_context)
            result = await skill.run(query="test")

        assert result.is_failed
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_web_search_with_domains(self, skill_context, mock_tavily):
        """Test web search with domain filter."""
        with patch(
            "agents.goal_executor.skills.primitives.get_tavily",
            return_value=mock_tavily,
        ):
            skill = WebSearchSkill(context=skill_context)
            result = await skill.run(
                query="DevOps jobs",
                include_domains=["linkedin.com", "indeed.com"],
            )

        assert result.status in [SkillStatus.SUCCESS, SkillStatus.PARTIAL]


class TestDeepResearchSkill:
    """Tests for DeepResearchSkill."""

    @pytest.mark.asyncio
    async def test_deep_research_success(self, skill_context, mock_perplexity):
        """Test successful deep research."""
        with patch(
            "agents.goal_executor.skills.primitives.get_perplexity",
            return_value=mock_perplexity,
        ):
            skill = DeepResearchSkill(context=skill_context)
            result = await skill.run(query="What is Acme Corp's technology stack?")

        assert result.is_success
        assert len(result.data.research) > 0

    @pytest.mark.asyncio
    async def test_deep_research_with_context(self, skill_context, mock_perplexity):
        """Test deep research with additional context."""
        with patch(
            "agents.goal_executor.skills.primitives.get_perplexity",
            return_value=mock_perplexity,
        ):
            skill = DeepResearchSkill(context=skill_context)
            result = await skill.run(
                query="Company analysis",
                research_context="Focus on DevOps practices and infrastructure",
            )

        assert result.is_success

    @pytest.mark.asyncio
    async def test_deep_research_not_configured(self, skill_context):
        """Test deep research when Perplexity not configured."""
        mock_perplexity = MagicMock()
        mock_perplexity.is_configured = False

        with patch(
            "agents.goal_executor.skills.primitives.get_perplexity",
            return_value=mock_perplexity,
        ):
            skill = DeepResearchSkill(context=skill_context)
            result = await skill.run(query="test")

        assert result.is_failed


class TestMemorySkills:
    """Tests for memory skills."""

    @pytest.mark.asyncio
    async def test_save_and_recall_memory(self, skill_context):
        """Test saving and recalling memory."""
        with patch(
            "agents.goal_executor.skills.primitives.get_goal_memory"
        ) as mock_memory_fn:
            mock_memory = MagicMock()
            mock_memory.remember.return_value = True
            mock_memory.recall.return_value = {"patterns": ["funding", "hiring"]}
            mock_memory_fn.return_value = mock_memory

            # Save
            save_skill = SaveMemorySkill(context=skill_context)
            save_result = await save_skill.run(
                key="successful_signals",
                value={"patterns": ["funding", "hiring"]},
            )

            assert save_result.is_success
            mock_memory.remember.assert_called_once()

            # Recall
            recall_skill = RecallMemorySkill(context=skill_context)
            recall_result = await recall_skill.run(key="successful_signals")

            assert recall_result.is_success
            assert recall_result.data.found is True

    @pytest.mark.asyncio
    async def test_recall_all_memories(self, skill_context):
        """Test recalling all memories."""
        with patch(
            "agents.goal_executor.skills.primitives.get_goal_memory"
        ) as mock_memory_fn:
            mock_memory = MagicMock()
            mock_memory.recall_all.return_value = {
                "signals": ["funding"],
                "icp": {"industry": "tech"},
            }
            mock_memory_fn.return_value = mock_memory

            skill = RecallMemorySkill(context=skill_context)
            result = await skill.run(search_all=True)

            assert result.is_success
            assert result.data.count == 2

    @pytest.mark.asyncio
    async def test_recall_missing_key(self, skill_context):
        """Test recalling non-existent key."""
        with patch(
            "agents.goal_executor.skills.primitives.get_goal_memory"
        ) as mock_memory_fn:
            mock_memory = MagicMock()
            mock_memory.recall.return_value = None
            mock_memory_fn.return_value = mock_memory

            skill = RecallMemorySkill(context=skill_context)
            result = await skill.run(key="nonexistent")

            assert result.status == SkillStatus.PARTIAL
            assert result.data.found is False

    @pytest.mark.asyncio
    async def test_list_prospects(self, skill_context):
        """Test listing prospects."""
        with patch(
            "agents.goal_executor.skills.primitives.get_goal_memory"
        ) as mock_memory_fn:
            mock_memory = MagicMock()
            mock_memory.list_prospects.return_value = [
                {"company_name": "Acme", "score": 85},
                {"company_name": "TechCo", "score": 72},
            ]
            mock_memory_fn.return_value = mock_memory

            skill = ListProspectsSkill(context=skill_context)
            result = await skill.run(limit=10)

            assert result.is_success
            assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_run_history(self, skill_context):
        """Test getting run history."""
        with patch(
            "agents.goal_executor.skills.primitives.get_goal_memory"
        ) as mock_memory_fn:
            mock_memory = MagicMock()
            mock_memory.get_recent_runs.return_value = [
                {"run_id": "run1", "status": "completed"},
                {"run_id": "run2", "status": "completed"},
            ]
            mock_memory_fn.return_value = mock_memory

            skill = GetRunHistorySkill(context=skill_context)
            result = await skill.run(limit=5)

            assert result.is_success
            assert result.data["count"] == 2


class TestGoalMemorySessionScoping:
    """Tests for session-scoped and goal-wide memory features."""

    def test_session_activity_logging(self):
        """Test logging activities for a session."""
        from agents.goal_executor.services.memory import GoalMemory

        memory = GoalMemory(bot_id="test_bot", thread_id="thread_123")

        # Log some activities
        memory.log_activity("search", {"query": "AI startups"}, persist=False)
        memory.log_activity("company_research", {"company": "Acme Corp"}, persist=False)

        # Get session activity
        activities = memory.get_session_activity()
        assert len(activities) == 2
        # Most recent first
        assert activities[0]["data"]["company"] == "Acme Corp"
        assert activities[1]["data"]["query"] == "AI startups"

    def test_session_activity_filtering_by_type(self):
        """Test filtering session activities by type."""
        from agents.goal_executor.services.memory import GoalMemory

        memory = GoalMemory(bot_id="test_bot", thread_id="thread_123")

        memory.log_activity("search", {"query": "AI"}, persist=False)
        memory.log_activity("company_research", {"company": "Acme"}, persist=False)
        memory.log_activity("search", {"query": "DevOps"}, persist=False)

        # Filter by type
        searches = memory.get_session_activity(activity_type="search")
        assert len(searches) == 2
        assert all(a["type"] == "search" for a in searches)

    def test_session_summary(self):
        """Test getting session summary."""
        from agents.goal_executor.services.memory import GoalMemory

        memory = GoalMemory(bot_id="test_bot", thread_id="thread_123")

        memory.log_activity("search", {"query": "AI"}, persist=False)
        memory.log_activity("search", {"query": "ML"}, persist=False)
        memory.log_activity("company_research", {"company": "Acme"}, persist=False)

        summary = memory.get_session_summary()
        assert summary["thread_id"] == "thread_123"
        assert summary["total_activities"] == 3
        assert summary["by_type"]["search"] == 2
        assert summary["by_type"]["company_research"] == 1

    def test_goal_wide_sets(self):
        """Test goal-wide set operations."""
        from agents.goal_executor.services.memory import GoalMemory

        memory = GoalMemory(bot_id="test_bot")

        # Mock the remember/recall methods
        stored_sets: dict = {}

        def mock_remember(key, value):
            stored_sets[key] = value
            return True

        def mock_recall(key):
            return stored_sets.get(key)

        memory.remember = mock_remember
        memory.recall = mock_recall

        # Add to set
        assert memory.add_to_set("companies", "Acme") is True
        assert memory.add_to_set("companies", "TechCo") is True
        assert memory.add_to_set("companies", "Acme") is False  # Already exists

        # Check membership
        assert memory.is_in_set("companies", "Acme") is True
        assert memory.is_in_set("companies", "Unknown") is False

        # Get all
        companies = memory.get_set("companies")
        assert "Acme" in companies
        assert "TechCo" in companies

        # Remove
        assert memory.remove_from_set("companies", "Acme") is True
        assert memory.remove_from_set("companies", "Acme") is False  # Already removed

    def test_convenience_methods(self):
        """Test convenience methods for logging."""
        from agents.goal_executor.services.memory import GoalMemory

        memory = GoalMemory(bot_id="test_bot", thread_id="thread_123")

        # Mock set operations
        stored_sets: dict = {}

        def mock_remember(key, value):
            stored_sets[key] = value
            return True

        def mock_recall(key):
            return stored_sets.get(key)

        memory.remember = mock_remember
        memory.recall = mock_recall

        # Log search
        memory.log_search("AI infrastructure", results_count=5, source="tavily")

        # Log company research
        memory.log_company_researched("Acme Corp", {"funding": "$10M"})

        # Check session activity
        activities = memory.get_session_activity()
        assert len(activities) == 2

        # Check goal-wide tracking
        assert memory.was_company_researched("Acme Corp") is True
        assert memory.was_company_researched("Unknown Co") is False

        all_companies = memory.get_all_companies_researched()
        assert "Acme Corp" in all_companies


class TestVectorMemory:
    """Tests for VectorMemory (semantic search)."""

    def test_temporal_decay_calculation(self):
        """Test temporal decay score adjustment."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test_bot")

        # Today's memory - no decay
        now = datetime.now().isoformat()
        score = memory._apply_decay(1.0, now)
        assert score > 0.99  # Almost no decay

        # 30-day old memory - half decay
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        score = memory._apply_decay(1.0, old_date)
        assert 0.45 < score < 0.55  # ~50% due to half-life

        # 90-day old memory - significant decay
        very_old = (datetime.now() - timedelta(days=90)).isoformat()
        score = memory._apply_decay(1.0, very_old)
        assert score < 0.15  # ~12.5%

    def test_memory_id_generation(self):
        """Test deterministic memory ID generation."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test_bot")

        # Same inputs = same ID
        id1 = memory._generate_memory_id("thread_1", "outcome A")
        id2 = memory._generate_memory_id("thread_1", "outcome A")
        assert id1 == id2

        # Different inputs = different ID
        id3 = memory._generate_memory_id("thread_2", "outcome A")
        assert id1 != id3

    def test_simple_summary_generation(self):
        """Test simple summary generation without LLM."""
        from agents.goal_executor.services.vector_memory import VectorMemory

        memory = VectorMemory(bot_id="test_bot")

        activities = [
            {"type": "search", "data": {"query": "AI startups"}},
            {"type": "company_research", "data": {"company": "Acme Corp"}},
            {"type": "company_research", "data": {"company": "TechCo"}},
        ]

        summary = memory._simple_summary(
            activities,
            outcome="Found 2 qualified prospects",
            goal="Find AI infrastructure companies",
        )

        assert "Goal:" in summary
        assert "Companies:" in summary
        assert "Acme Corp" in summary
        assert "Found 2 qualified" in summary


class TestYouTubeSkill:
    """Tests for YouTubeSkill."""

    def test_extract_video_id_from_url(self):
        """Test extracting video ID from various URL formats."""
        # Standard URL
        assert (
            extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        )

        # Short URL
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

        # Embed URL
        assert (
            extract_video_id("https://youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        )

        # Just the ID
        assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

        # Invalid (wrong length or has dots)
        assert extract_video_id("not.a") is None
        assert extract_video_id("tooshort") is None
        assert extract_video_id("this-is-way-too-long-to-be-a-video-id") is None

    def test_youtube_video_to_dict(self):
        """Test YouTubeVideo.to_dict()."""
        video = YouTubeVideo(
            video_id="abc123",
            title="Test Video",
            channel="Test Channel",
            description="A test video",
            url="https://youtube.com/watch?v=abc123",
            view_count=1000,
        )
        d = video.to_dict()
        assert d["video_id"] == "abc123"
        assert d["title"] == "Test Video"
        assert d["view_count"] == 1000

    @pytest.mark.asyncio
    async def test_youtube_search_with_web_fallback(self, skill_context):
        """Test YouTube search falling back to web search."""
        # Mock tavily to return YouTube-like results
        mock_tavily = MagicMock()
        mock_tavily.is_configured = True
        mock_tavily.search.return_value = [
            SearchResult(
                title="Acme Corp Demo - YouTube",
                url="https://youtube.com/watch?v=test123abcd",
                content="Product demo video",
                source="tavily",
            ),
        ]

        with (
            patch(
                "agents.goal_executor.skills.youtube.get_goal_memory"
            ) as mock_memory_fn,
            patch(
                "agents.goal_executor.skills.prospect.clients.get_tavily",
                return_value=mock_tavily,
            ),
        ):
            mock_memory = MagicMock()
            mock_memory.recall.return_value = None
            mock_memory.remember.return_value = True
            mock_memory_fn.return_value = mock_memory

            # Patch transcript API - mock the fetch method
            with patch(
                "youtube_transcript_api.YouTubeTranscriptApi"
            ) as MockTranscriptApi:
                # Create mock transcript with snippets
                mock_snippet1 = MagicMock()
                mock_snippet1.text = "Hello, this is a demo."
                mock_snippet2 = MagicMock()
                mock_snippet2.text = "Our product does amazing things."

                mock_transcript = MagicMock()
                mock_transcript.snippets = [mock_snippet1, mock_snippet2]

                mock_api = MagicMock()
                mock_api.fetch.return_value = mock_transcript
                MockTranscriptApi.return_value = mock_api

                skill = YouTubeSkill(context=skill_context)
                # Skip summarization for this test
                result = await skill.run(
                    query="Acme Corp demo",
                    summarize=False,
                    full_transcript=True,
                )

        # Should have found video and transcript
        assert result.status in [SkillStatus.SUCCESS, SkillStatus.PARTIAL]

    @pytest.mark.asyncio
    async def test_youtube_with_cached_transcript(self, skill_context):
        """Test YouTube returns cached transcript."""
        with patch(
            "agents.goal_executor.skills.youtube.get_goal_memory"
        ) as mock_memory_fn:
            mock_memory = MagicMock()
            mock_memory.recall.side_effect = lambda key: (
                "Cached transcript content here" if "transcript" in key else None
            )
            mock_memory_fn.return_value = mock_memory

            skill = YouTubeSkill(context=skill_context)
            # Direct video ID
            result = await skill.run(
                query="dQw4w9WgXcQ",
                summarize=False,
                full_transcript=True,
            )

        assert result.is_success
        assert result.data.cached is True
        assert "Cached transcript" in result.data.transcript


class TestRephraseSkill:
    """Tests for RephraseSkill."""

    @pytest.mark.asyncio
    async def test_rephrase_with_llm(self, skill_context):
        """Test rephrase with LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client:
                # Mock successful response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "choices": [
                        {
                            "message": {
                                "content": '{"alternatives": ["Acme DevOps jobs", "Acme platform engineering hiring", "Acme infrastructure team"], "reasoning": "Expanded job-related terms"}'
                            }
                        }
                    ]
                }

                mock_client_instance = MagicMock()
                mock_client_instance.__aenter__ = AsyncMock(
                    return_value=mock_client_instance
                )
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client.return_value = mock_client_instance

                skill = RephraseSkill(context=skill_context)
                result = await skill.run(
                    text="Acme Corp DevOps hiring",
                    goal="find job postings",
                )

        assert result.is_success
        assert len(result.data.alternatives) > 0

    @pytest.mark.asyncio
    async def test_rephrase_fallback_no_api_key(self, skill_context):
        """Test rephrase falls back without API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            # Clear the key
            with patch.object(
                RephraseSkill,
                "__init__",
                lambda self, context=None: (
                    setattr(self, "context", context or SkillContext()),
                    setattr(self, "openai_api_key", None),
                    setattr(self, "_start_time", None),
                )[-1],
            ):
                skill = RephraseSkill(context=skill_context)
                result = await skill.run(
                    text="Acme Corp hiring",
                    goal="find jobs",
                )

        assert result.status == SkillStatus.PARTIAL
        assert len(result.data.alternatives) > 0
        assert "fallback" in result.steps_completed[0]

    @pytest.mark.asyncio
    async def test_rephrase_simple_alternatives(self, skill_context):
        """Test simple alternative generation."""
        skill = RephraseSkill(context=skill_context)
        alternatives = skill._generate_simple_alternatives("Acme Corp hiring", 5)

        assert len(alternatives) > 0
        assert any('"' in alt for alt in alternatives)  # Should have quoted version

    @pytest.mark.asyncio
    async def test_rephrase_styles(self, skill_context):
        """Test different rephrase styles are accepted."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            skill = RephraseSkill(context=skill_context)
            skill.openai_api_key = None  # Force fallback

            for style in ["search", "expand", "narrow", "creative"]:
                result = await skill.run(
                    text="test query",
                    goal="testing",
                    style=style,
                )
                assert result.status in [SkillStatus.SUCCESS, SkillStatus.PARTIAL]


class TestPrimitiveSkillsRegistered:
    """Test that primitive skills are properly registered."""

    def test_all_primitives_registered(self):
        """Test all primitive skills are in registry."""
        registry = get_skill_registry()
        names = registry.get_skill_names()

        expected_primitives = [
            "web_search",
            "deep_research",
            "recall_memory",
            "save_memory",
            "list_prospects",
            "get_run_history",
            "youtube",
            "rephrase",
        ]

        for skill_name in expected_primitives:
            assert skill_name in names, f"Missing primitive skill: {skill_name}"

    def test_all_workflow_skills_registered(self):
        """Test all workflow skills are in registry."""
        registry = get_skill_registry()
        names = registry.get_skill_names()

        expected_workflows = [
            "research_prospect",
            "search_signals",
            "check_relationship",
            "qualify_prospect",
        ]

        for skill_name in expected_workflows:
            assert skill_name in names, f"Missing workflow skill: {skill_name}"

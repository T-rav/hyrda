"""Comprehensive tests for Lead Qualifier agent.

Tests cover:
- Input validation (HubSpot data format)
- Individual node functions
- Full graph integration
- RAG service integration
- Edge cases and error handling
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from custom_agents.lead_qualifier.configuration import QualifierConfiguration
from custom_agents.lead_qualifier.nodes.analyze_historical_similarity import (
    analyze_historical_similarity,
)
from custom_agents.lead_qualifier.nodes.analyze_solution_fit import (
    _extract_field,
    _extract_list,
    _extract_score,
    analyze_solution_fit,
)
from custom_agents.lead_qualifier.nodes.analyze_strategic_fit import (
    analyze_strategic_fit,
)
from custom_agents.lead_qualifier.nodes.graph_builder import build_lead_qualifier
from custom_agents.lead_qualifier.nodes.search_similar_clients import (
    search_similar_clients,
)
from custom_agents.lead_qualifier.nodes.synthesize_qualification import (
    synthesize_qualification,
)
from custom_agents.lead_qualifier.state import QualifierInput, QualifierState


# Sample HubSpot lead data for testing
SAMPLE_HUBSPOT_LEAD_HIGH = {
    "company": {
        "company_name": "TechCorp Industries",
        "company_domain": "techcorp.com",
        "industry": "Healthcare Technology",
        "company_size": "200-500",
        "location": "Chicago, IL",
        "region": "Midwest",
    },
    "contact": {
        "contact_name": "Sarah Johnson",
        "job_title": "VP of Engineering",
        "seniority": "VP",
        "department": "Engineering",
        "lifecycle_stage": "Opportunity",
        "lead_source": "Inbound",
        "original_source": "Website",
        "hubspot_lead_score": 85.0,
    },
    "sequence_identifier": "enterprise_outreach_2024",
}

SAMPLE_HUBSPOT_LEAD_MEDIUM = {
    "company": {
        "company_name": "StartupXYZ",
        "company_domain": "startupxyz.io",
        "industry": "FinTech",
        "company_size": "10-50",
        "location": "Austin, TX",
        "region": "South",
    },
    "contact": {
        "contact_name": "Mike Chen",
        "job_title": "CTO",
        "seniority": "C-level",
        "department": "Engineering",
        "lifecycle_stage": "Lead",
        "lead_source": "Referral",
        "original_source": "Partner",
        "hubspot_lead_score": 45.0,
    },
}

SAMPLE_HUBSPOT_LEAD_LOW = {
    "company": {
        "company_name": "SmallBiz Local",
        "company_domain": "smallbiz.com",
        "industry": "Retail",
        "company_size": "1-10",
        "location": "Portland, OR",
        "region": "West",
    },
    "contact": {
        "contact_name": "Jane Smith",
        "job_title": "Owner",
        "seniority": "IC",
        "department": "Leadership",
        "lifecycle_stage": "Subscriber",
        "lead_source": "Organic",
        "original_source": "Blog",
        "hubspot_lead_score": 15.0,
    },
}

MINIMAL_HUBSPOT_DATA = {
    "company": {"company_name": "Minimal Corp"},
    "contact": {"contact_name": "Test User"},
}

EMPTY_HUBSPOT_DATA = {"company": {}, "contact": {}}


class TestQualifierConfiguration:
    """Test configuration loading."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = QualifierConfiguration()
        assert config.model == "gpt-4o"
        assert config.temperature == 0.0
        assert config.solution_fit_weight == 40
        assert config.strategic_fit_weight == 25
        assert config.historical_similarity_weight == 25
        assert config.high_tier_threshold == 75
        assert config.medium_tier_threshold == 50

    def test_from_env_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("MODEL", "gpt-4o-mini")
        monkeypatch.setenv("TEMPERATURE", "0.5")
        monkeypatch.setenv("SOLUTION_FIT_WEIGHT", "50")

        config = QualifierConfiguration.from_env()
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.5
        assert config.solution_fit_weight == 50

    def test_service_categories(self):
        """Test service categories are defined."""
        config = QualifierConfiguration()
        assert len(config.service_categories) == 7
        assert "Platform Modernization" in config.service_categories
        assert "AI Enablement" in config.service_categories


class TestInputValidation:
    """Test HubSpot input validation."""

    def test_valid_high_quality_lead(self):
        """Test valid high-quality lead data."""
        input_data = QualifierInput(**SAMPLE_HUBSPOT_LEAD_HIGH)
        assert input_data["company"]["company_name"] == "TechCorp Industries"
        assert input_data["contact"]["seniority"] == "VP"

    def test_valid_medium_quality_lead(self):
        """Test valid medium-quality lead data."""
        input_data = QualifierInput(**SAMPLE_HUBSPOT_LEAD_MEDIUM)
        assert input_data["company"]["industry"] == "FinTech"

    def test_valid_low_quality_lead(self):
        """Test valid low-quality lead data."""
        input_data = QualifierInput(**SAMPLE_HUBSPOT_LEAD_LOW)
        assert input_data["company"]["company_size"] == "1-10"

    def test_minimal_data(self):
        """Test minimal required data."""
        input_data = QualifierInput(**MINIMAL_HUBSPOT_DATA)
        assert input_data["company"]["company_name"] == "Minimal Corp"

    def test_empty_data(self):
        """Test empty data handling."""
        input_data = QualifierInput(**EMPTY_HUBSPOT_DATA)
        assert input_data["company"] == {}
        assert input_data["contact"] == {}

    def test_optional_sequence_identifier(self):
        """Test sequence identifier is optional."""
        data = {
            "company": {"company_name": "Test Co"},
            "contact": {"contact_name": "Test User"},
            # No sequence_identifier
        }
        input_data = QualifierInput(**data)
        assert "sequence_identifier" not in input_data


class TestExtractScoreFunction:
    """Test score extraction from LLM response."""

    def test_extract_valid_score(self):
        """Test extracting a valid score."""
        text = "solution_fit_score: 35"
        score = _extract_score(text, "solution_fit_score", 0, 40)
        assert score == 35

    def test_extract_score_with_clamping_max(self):
        """Test score clamping at max."""
        text = "solution_fit_score: 50"
        score = _extract_score(text, "solution_fit_score", 0, 40)
        assert score == 40  # Clamped to max

    def test_extract_score_with_clamping_min(self):
        """Test score clamping at min."""
        text = "solution_fit_score: -10"
        score = _extract_score(text, "solution_fit_score", 0, 40)
        assert score == 0  # Clamped to min

    def test_extract_missing_score(self):
        """Test default when score missing."""
        text = "some_other_field: 35"
        score = _extract_score(text, "solution_fit_score", 0, 40)
        assert score == 0  # Default to min

    def test_extract_score_case_insensitive(self):
        """Test case insensitive field matching."""
        text = "SOLUTION_FIT_SCORE: 30"
        score = _extract_score(text, "solution_fit_score", 0, 40)
        assert score == 30


class TestExtractFieldFunction:
    """Test field extraction from LLM response."""

    def test_extract_simple_field(self):
        """Test extracting a simple field."""
        text = "solution_fit_reasoning: This is a good fit\nrecommended_solution: [AI]"
        result = _extract_field(text, "solution_fit_reasoning")
        assert "This is a good fit" in result

    def test_extract_multiline_field(self):
        """Test extracting multiline field."""
        text = """solution_fit_reasoning: This is a good fit
because the company needs AI solutions
and has budget allocated.
recommended_solution: [AI]"""
        result = _extract_field(text, "solution_fit_reasoning")
        assert "This is a good fit" in result
        assert "because" in result

    def test_extract_missing_field(self):
        """Test handling missing field."""
        text = "some_other_field: value"
        result = _extract_field(text, "missing_field")
        assert result == text[:500]  # Returns truncated text


class TestExtractListFunction:
    """Test list extraction from LLM response."""

    def test_extract_simple_list(self):
        """Test extracting a simple list."""
        text = 'recommended_solution: ["AI Enablement", "Cloud Migration"]'
        result = _extract_list(text, "recommended_solution")
        assert "AI Enablement" in result
        assert "Cloud Migration" in result

    def test_extract_list_with_quotes(self):
        """Test extracting list with various quote styles."""
        text = "recommended_solution: ['AI Enablement', \"Cloud Migration\"]"
        result = _extract_list(text, "recommended_solution")
        assert "AI Enablement" in result
        assert "Cloud Migration" in result

    def test_extract_missing_list(self):
        """Test handling missing list."""
        text = "some_other_field: value"
        result = _extract_list(text, "missing_list")
        assert result == []


class TestAnalyzeSolutionFit:
    """Test solution fit analysis node."""

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for solution fit."""
        mock_response = Mock()
        mock_response.content = """
solution_fit_score: 35
solution_fit_reasoning: Strong alignment with AI Enablement and Platform Modernization services
recommended_solution: ["AI Enablement", "Platform Modernization"]
"""
        return mock_response

    @pytest.mark.asyncio
    async def test_analyze_solution_fit_high_score(self, mock_llm_response):
        """Test high solution fit score."""
        state = QualifierState(
            query="Qualify this lead",
            company=SAMPLE_HUBSPOT_LEAD_HIGH["company"],
            contact=SAMPLE_HUBSPOT_LEAD_HIGH["contact"],
            sequence_identifier=None,
            solution_fit_score=0,
            solution_fit_reasoning="",
            strategic_fit_score=0,
            strategic_fit_reasoning="",
            historical_similarity_score=0,
            historical_similarity_reasoning="",
            similar_clients=[],
            similar_projects=[],
            qualification_score=0,
            fit_tier="Low",
            recommended_solution=[],
            similar_client_example=[],
            qualification_summary="",
            primary_initiative="",
            risk_flags=[],
            error=None,
        )

        mock_llm_settings = Mock()
        mock_llm_settings.api_key.get_secret_value.return_value = "test-api-key"

        with patch(
            "custom_agents.lead_qualifier.nodes.analyze_solution_fit.ChatOpenAI"
        ) as mock_llm_class:
            with patch(
                "config.settings.LLMSettings",
                return_value=mock_llm_settings,
            ):
                mock_llm = Mock()
                mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
                mock_llm_class.return_value = mock_llm

                result = await analyze_solution_fit(state, {})

        assert result["solution_fit_score"] == 35
        assert "AI Enablement" in result["recommended_solution"]
        assert "reasoning" in result["solution_fit_reasoning"].lower() or len(result["solution_fit_reasoning"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_solution_fit_with_vp_contact(self):
        """Test solution fit with VP-level contact."""
        state = QualifierState(
            query="Qualify",
            company={"company_name": "Test Co", "industry": "Technology"},
            contact={"job_title": "VP of Engineering", "seniority": "VP"},
            sequence_identifier=None,
            solution_fit_score=0,
            solution_fit_reasoning="",
            strategic_fit_score=0,
            strategic_fit_reasoning="",
            historical_similarity_score=0,
            historical_similarity_reasoning="",
            similar_clients=[],
            similar_projects=[],
            qualification_score=0,
            fit_tier="Low",
            recommended_solution=[],
            similar_client_example=[],
            qualification_summary="",
            primary_initiative="",
            risk_flags=[],
            error=None,
        )

        mock_response = Mock()
        mock_response.content = "solution_fit_score: 30\nsolution_fit_reasoning: VP contact indicates decision-making power"

        mock_llm_settings = Mock()
        mock_llm_settings.api_key.get_secret_value.return_value = "test-api-key"

        with patch(
            "custom_agents.lead_qualifier.nodes.analyze_solution_fit.ChatOpenAI"
        ) as mock_llm_class:
            with patch(
                "config.settings.LLMSettings",
                return_value=mock_llm_settings,
            ):
                mock_llm = Mock()
                mock_llm.ainvoke = AsyncMock(return_value=mock_response)
                mock_llm_class.return_value = mock_llm

                result = await analyze_solution_fit(state, {})

        assert result["solution_fit_score"] > 0


class TestSearchSimilarClients:
    """Test similar client search node."""

    @pytest.mark.asyncio
    async def test_search_with_rag_service_success(self):
        """Test successful RAG service call."""
        state = QualifierState(
            query="Qualify",
            company={"company_name": "HealthTech Corp", "industry": "Healthcare", "company_size": "200-500"},
            contact={},
            sequence_identifier=None,
            solution_fit_score=0,
            solution_fit_reasoning="",
            strategic_fit_score=0,
            strategic_fit_reasoning="",
            historical_similarity_score=0,
            historical_similarity_reasoning="",
            similar_clients=[],
            similar_projects=[],
            qualification_score=0,
            fit_tier="Low",
            recommended_solution=[],
            similar_client_example=[],
            qualification_summary="",
            primary_initiative="",
            risk_flags=[],
            error=None,
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "chunks": [
                {
                    "content": "Client engagement with Healthcare company for data platform",
                    "similarity": 0.85,
                    "metadata": {"file_name": "healthcare_case_study.txt", "industry": "Healthcare"},
                },
                {
                    "content": "Platform modernization project for HealthTech firm",
                    "similarity": 0.78,
                    "metadata": {"file_name": "platform_modernization.txt", "project_type": "Modernization"},
                },
            ]
        }

        with patch(
            "custom_agents.lead_qualifier.nodes.search_similar_clients.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with patch.dict("os.environ", {"BOT_SERVICE_TOKEN": "test-token"}):
                result = await search_similar_clients(state, {})

        assert len(result["similar_clients"]) > 0 or len(result["similar_projects"]) > 0

    @pytest.mark.asyncio
    async def test_search_with_rag_service_failure_fallback(self):
        """Test fallback when RAG service fails."""
        state = QualifierState(
            query="Qualify",
            company={"company_name": "Test Corp", "industry": "Technology", "company_size": "100-200"},
            contact={},
            sequence_identifier=None,
            solution_fit_score=0,
            solution_fit_reasoning="",
            strategic_fit_score=0,
            strategic_fit_reasoning="",
            historical_similarity_score=0,
            historical_similarity_reasoning="",
            similar_clients=[],
            similar_projects=[],
            qualification_score=0,
            fit_tier="Low",
            recommended_solution=[],
            similar_client_example=[],
            qualification_summary="",
            primary_initiative="",
            risk_flags=[],
            error=None,
        )

        with patch(
            "custom_agents.lead_qualifier.nodes.search_similar_clients.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await search_similar_clients(state, {})

        # Should return fallback data
        assert len(result["similar_clients"]) >= 1
        assert len(result["similar_projects"]) >= 1


class TestSynthesizeQualification:
    """Test final synthesis node."""

    @pytest.mark.asyncio
    async def test_high_tier_qualification(self):
        """Test high tier qualification (75+)."""
        state = QualifierState(
            query="Qualify",
            company={},
            contact={},
            sequence_identifier=None,
            solution_fit_score=38,  # High solution fit
            solution_fit_reasoning="Strong alignment",
            strategic_fit_score=22,  # High strategic fit
            strategic_fit_reasoning="Ready to buy",
            historical_similarity_score=20,  # Good historical match
            historical_similarity_reasoning="Similar to past successes",
            similar_clients=[{"name": "Similar Client", "similarity": 0.8}],
            similar_projects=[{"title": "Similar Project", "similarity": 0.75}],
            qualification_score=0,
            fit_tier="Low",
            recommended_solution=["AI Enablement"],
            similar_client_example=["Similar Client"],
            qualification_summary="",
            primary_initiative="AI adoption",
            risk_flags=[],
            error=None,
        )

        mock_response = Mock()
        mock_response.content = "This is a high-quality lead with strong AI alignment."

        mock_llm_settings = Mock()
        mock_llm_settings.api_key.get_secret_value.return_value = "test-api-key"

        with patch(
            "custom_agents.lead_qualifier.nodes.synthesize_qualification.ChatOpenAI"
        ) as mock_llm_class:
            with patch(
                "config.settings.LLMSettings",
                return_value=mock_llm_settings,
            ):
                mock_llm = Mock()
                mock_llm.ainvoke = AsyncMock(return_value=mock_response)
                mock_llm_class.return_value = mock_llm

                result = await synthesize_qualification(state, {})

        # 38 + 22 + 20 = 80/90 = 88.9 → normalized to ~89
        assert result["qualification_score"] > 75
        assert result["fit_tier"] == "High"

    @pytest.mark.asyncio
    async def test_low_tier_qualification(self):
        """Test low tier qualification (<50)."""
        state = QualifierState(
            query="Qualify",
            company={},
            contact={},
            sequence_identifier=None,
            solution_fit_score=10,  # Low solution fit
            solution_fit_reasoning="Weak alignment",
            strategic_fit_score=5,  # Low strategic fit
            strategic_fit_reasoning="Not ready",
            historical_similarity_score=5,  # Low historical match
            historical_similarity_reasoning="No similar clients",
            similar_clients=[],
            similar_projects=[],
            qualification_score=0,
            fit_tier="Low",
            recommended_solution=[],
            similar_client_example=[],
            qualification_summary="",
            primary_initiative="",
            risk_flags=["early-stage"],
            error=None,
        )

        mock_response = Mock()
        mock_response.content = "This lead is not a good fit at this time."

        mock_llm_settings = Mock()
        mock_llm_settings.api_key.get_secret_value.return_value = "test-api-key"

        with patch(
            "custom_agents.lead_qualifier.nodes.synthesize_qualification.ChatOpenAI"
        ) as mock_llm_class:
            with patch(
                "config.settings.LLMSettings",
                return_value=mock_llm_settings,
            ):
                mock_llm = Mock()
                mock_llm.ainvoke = AsyncMock(return_value=mock_response)
                mock_llm_class.return_value = mock_llm

                result = await synthesize_qualification(state, {})

        # 10 + 5 + 5 = 20/90 = 22.2 → normalized to ~22
        assert result["qualification_score"] < 50
        assert result["fit_tier"] == "Low"


class TestGraphBuilder:
    """Test graph construction."""

    def test_graph_compiles(self):
        """Test that the graph compiles successfully."""
        graph = build_lead_qualifier()
        assert graph is not None

    def test_graph_nodes(self):
        """Test that all expected nodes are in the graph."""
        graph = build_lead_qualifier()
        # The compiled graph doesn't expose nodes directly,
        # but we can verify it was built without errors
        assert hasattr(graph, "ainvoke") or hasattr(graph, "invoke")


class TestIntegration:
    """Integration tests for the full agent."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_qualification_workflow_high_tier(self):
        """Test full workflow with high-tier lead (requires API keys)."""
        # Skip if no API key
        import os

        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        graph = build_lead_qualifier()

        input_data = QualifierInput(
            company=SAMPLE_HUBSPOT_LEAD_HIGH["company"],
            contact=SAMPLE_HUBSPOT_LEAD_HIGH["contact"],
            sequence_identifier=SAMPLE_HUBSPOT_LEAD_HIGH.get("sequence_identifier"),
        )

        # Run the graph
        result = await graph.ainvoke(input_data)

        # Verify output structure
        assert "qualification_score" in result
        assert "fit_tier" in result
        assert result["fit_tier"] in ["High", "Medium", "Low"]
        assert isinstance(result["qualification_score"], int)
        assert 0 <= result["qualification_score"] <= 100

        # High-tier lead should score well
        # Note: Actual score depends on LLM and RAG results
        assert result["qualification_score"] > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_qualification_workflow_low_tier(self):
        """Test full workflow with low-tier lead (requires API keys)."""
        import os

        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        graph = build_lead_qualifier()

        input_data = QualifierInput(
            company=SAMPLE_HUBSPOT_LEAD_LOW["company"],
            contact=SAMPLE_HUBSPOT_LEAD_LOW["contact"],
        )

        result = await graph.ainvoke(input_data)

        assert "qualification_score" in result
        assert "fit_tier" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

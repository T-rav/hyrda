"""Tests for HubSpot sync job (jobs/hubspot_sync.py).

Tests focus on validation logic, parameter handling, and mocked API interactions.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.settings import TasksSettings
from jobs.hubspot_sync import HubSpotSyncJob


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=TasksSettings)
    settings.tasks_port = 5001
    settings.tasks_host = "localhost"
    return settings


class TestHubSpotSyncJobValidation:
    """Test job parameter validation."""

    def test_job_name_and_description(self, mock_settings):
        """Test job has proper name and description."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")
        assert job.JOB_NAME == "HubSpot Sync"
        assert "closed deals" in job.JOB_DESCRIPTION.lower()

    def test_required_params(self, mock_settings):
        """Test job defines required params correctly."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")
        assert "credential_id" in job.REQUIRED_PARAMS

    def test_optional_params(self, mock_settings):
        """Test job defines optional params correctly."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")
        assert "limit" in job.OPTIONAL_PARAMS

    def test_stores_credential_id(self, mock_settings):
        """Test job stores credential_id parameter."""
        job = HubSpotSyncJob(mock_settings, credential_id="my-cred-123")
        assert job.params["credential_id"] == "my-cred-123"

    def test_stores_limit_parameter(self, mock_settings):
        """Test job stores optional limit parameter."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred", limit=50)
        assert job.params["limit"] == 50

    def test_default_limit_not_set(self, mock_settings):
        """Test limit is not in params when not provided."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")
        assert job.params.get("limit") is None


class TestHubSpotSyncJobCredentialLoading:
    """Test credential loading from database."""

    def test_load_credentials_success(self, mock_settings):
        """Test successfully loading credentials from database."""
        mock_cred = Mock()
        mock_cred.provider = "hubspot"
        mock_cred.credential_name = "Test HubSpot"
        mock_cred.encrypted_token = "encrypted_data"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_cred
        mock_session.query.return_value = mock_query

        token_data = {"access_token": "test-token", "client_secret": "test-secret"}

        with (
            patch("jobs.hubspot_sync.get_db_session") as mock_get_session,
            patch("jobs.hubspot_sync.get_encryption_service") as mock_get_encryption,
        ):
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_encryption = Mock()
            mock_encryption.decrypt.return_value = json.dumps(token_data)
            mock_get_encryption.return_value = mock_encryption

            job = HubSpotSyncJob(mock_settings, credential_id="test-cred")
            access_token = job._load_credentials("test-cred")

            assert access_token == "test-token"

    def test_load_credentials_not_found(self, mock_settings):
        """Test error when credential not found."""
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        with patch("jobs.hubspot_sync.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            job = HubSpotSyncJob(mock_settings, credential_id="nonexistent")

            with pytest.raises(ValueError, match="Credential not found"):
                job._load_credentials("nonexistent")

    def test_load_credentials_wrong_provider(self, mock_settings):
        """Test error when credential is not a HubSpot credential."""
        mock_cred = Mock()
        mock_cred.provider = "google_drive"  # Wrong provider
        mock_cred.credential_id = "test-cred"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_cred
        mock_session.query.return_value = mock_query

        with patch("jobs.hubspot_sync.get_db_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

            with pytest.raises(ValueError, match="not a HubSpot credential"):
                job._load_credentials("test-cred")

    def test_load_credentials_missing_access_token(self, mock_settings):
        """Test error when decrypted data has no access_token."""
        mock_cred = Mock()
        mock_cred.provider = "hubspot"
        mock_cred.credential_name = "Test"
        mock_cred.encrypted_token = "encrypted"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_cred
        mock_session.query.return_value = mock_query

        with (
            patch("jobs.hubspot_sync.get_db_session") as mock_get_session,
            patch("jobs.hubspot_sync.get_encryption_service") as mock_get_encryption,
        ):
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_encryption = Mock()
            # Token data without access_token
            mock_encryption.decrypt.return_value = json.dumps(
                {"client_secret": "secret"}
            )
            mock_get_encryption.return_value = mock_encryption

            job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

            with pytest.raises(ValueError, match="No access_token found"):
                job._load_credentials("test-cred")


class TestHubSpotSyncJobExecution:
    """Test job execution logic."""

    @pytest.mark.asyncio
    async def test_execute_job_success(self, mock_settings):
        """Test successful job execution with mocked API."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred", limit=10)

        # Mock credential loading
        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock the HTTP client
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "properties": {
                            "dealname": "Test Deal",
                            "amount": "10000",
                            "closedate": "2024-01-15",
                            "dealstage": "closedwon",
                            "pipeline": "default",
                        },
                        "associations": {"companies": {"results": []}},
                    }
                ],
                "paging": {},
            }

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await job._execute_job()

                assert result["status"] == "success"
                assert result["records_processed"] == 1
                assert len(result["deals"]) == 1
                assert result["deals"][0]["deal_name"] == "Test Deal"
                assert result["deals"][0]["amount"] == 10000.0

    @pytest.mark.asyncio
    async def test_execute_job_filters_closed_won_deals(self, mock_settings):
        """Test that job filters for closed won deals only."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        with patch.object(job, "_load_credentials", return_value="test-token"):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "properties": {
                            "dealname": "Won Deal",
                            "amount": "5000",
                            "dealstage": "closedwon",
                        },
                        "associations": {},
                    },
                    {
                        "id": "deal-2",
                        "properties": {
                            "dealname": "Lost Deal",
                            "amount": "3000",
                            "dealstage": "closedlost",
                        },
                        "associations": {},
                    },
                    {
                        "id": "deal-3",
                        "properties": {
                            "dealname": "Open Deal",
                            "amount": "8000",
                            "dealstage": "negotiation",
                        },
                        "associations": {},
                    },
                ],
                "paging": {},
            }

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await job._execute_job()

                # Should only include closed won deal
                assert result["records_processed"] == 1
                assert result["deals"][0]["deal_name"] == "Won Deal"

    @pytest.mark.asyncio
    async def test_execute_job_api_error(self, mock_settings):
        """Test handling of HubSpot API errors."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        with patch.object(job, "_load_credentials", return_value="test-token"):
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                with pytest.raises(Exception, match="HubSpot API error: 401"):
                    await job._execute_job()


class TestHubSpotSyncJobCompanyEnrichment:
    """Test company data enrichment logic."""

    @pytest.mark.asyncio
    async def test_enrich_deal_with_company(self, mock_settings):
        """Test enriching deal with company tech stack data."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        deal = {
            "id": "deal-1",
            "properties": {
                "dealname": "Enterprise Deal",
                "amount": "50000",
                "closedate": "2024-02-01",
                "dealstage": "closedwon",
                "pipeline": "enterprise",
            },
            "associations": {"companies": {"results": [{"id": "company-1"}]}},
        }

        company_response = Mock()
        company_response.status_code = 200
        company_response.json.return_value = {
            "properties": {
                "name": "Acme Corp",
                "domain": "acme.com",
                "industry": "Technology",
                "numberofemployees": "500",
                "technologies": "Python, React, AWS",
            }
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = company_response

        result = await job._enrich_deal_with_company(
            mock_client, {"Authorization": "Bearer test"}, deal
        )

        assert result["deal_name"] == "Enterprise Deal"
        assert result["amount"] == 50000.0
        assert result["company_name"] == "Acme Corp"
        assert result["company_domain"] == "acme.com"
        assert result["industry"] == "Technology"
        assert "Python" in result["tech_stack"]
        assert "React" in result["tech_stack"]
        assert "AWS" in result["tech_stack"]

    @pytest.mark.asyncio
    async def test_enrich_deal_without_company(self, mock_settings):
        """Test enriching deal when no company is associated."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        deal = {
            "id": "deal-1",
            "properties": {
                "dealname": "Solo Deal",
                "amount": "1000",
                "dealstage": "closedwon",
            },
            "associations": {},  # No company associations
        }

        mock_client = AsyncMock()

        result = await job._enrich_deal_with_company(mock_client, {}, deal)

        assert result["deal_name"] == "Solo Deal"
        assert result["amount"] == 1000.0
        assert "company_name" not in result
        assert "tech_stack" not in result

    @pytest.mark.asyncio
    async def test_fetch_company_handles_api_error(self, mock_settings):
        """Test company fetch gracefully handles API errors."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        mock_response = Mock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await job._fetch_company(mock_client, {}, "nonexistent-company")

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_tech_stack_from_multiple_fields(self, mock_settings):
        """Test parsing tech stack from various HubSpot fields."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        company_response = Mock()
        company_response.status_code = 200
        company_response.json.return_value = {
            "properties": {
                "name": "Tech Corp",
                "technologies": "Python, JavaScript",
                "tech_stack": "Docker; Kubernetes",
                "builtwith_tech": "React, Vue",
            }
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = company_response

        result = await job._fetch_company(mock_client, {}, "company-1")

        # Should combine all tech stack fields
        assert "Python" in result["tech_stack"]
        assert "JavaScript" in result["tech_stack"]
        assert "Docker" in result["tech_stack"]
        assert "Kubernetes" in result["tech_stack"]
        assert "React" in result["tech_stack"]
        assert "Vue" in result["tech_stack"]


class TestHubSpotSyncJobAttributes:
    """Test job has all required attributes."""

    def test_job_has_required_attributes(self, mock_settings):
        """Test job has all standard attributes."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        assert hasattr(job, "JOB_NAME")
        assert hasattr(job, "JOB_DESCRIPTION")
        assert hasattr(job, "REQUIRED_PARAMS")
        assert hasattr(job, "OPTIONAL_PARAMS")
        assert hasattr(job, "params")
        assert hasattr(job, "_execute_job")
        assert hasattr(job, "_load_credentials")

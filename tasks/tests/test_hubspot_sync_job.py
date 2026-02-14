"""Tests for HubSpot sync job (jobs/hubspot_sync.py).

Tests focus on validation logic, parameter handling, mocked API interactions,
document building, owner fetching, and vector ingestion.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.settings import TasksSettings
from jobs.hubspot_sync import DEAL_PROPERTIES, HubSpotSyncJob


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
        assert "skip_vector_ingestion" in job.OPTIONAL_PARAMS

    def test_skip_vector_ingestion_param(self, mock_settings):
        """Test job accepts skip_vector_ingestion parameter."""
        job = HubSpotSyncJob(
            mock_settings, credential_id="test-cred", skip_vector_ingestion=True
        )
        assert job.params["skip_vector_ingestion"] is True

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
        job = HubSpotSyncJob(
            mock_settings,
            credential_id="test-cred",
            limit=10,
            skip_vector_ingestion=True,
        )

        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock pipelines response
            pipelines_response = Mock()
            pipelines_response.status_code = 200
            pipelines_response.json.return_value = {
                "results": [
                    {
                        "id": "pipeline-1",
                        "label": "New Business",
                        "stages": [
                            {
                                "id": "won-stage-id",
                                "label": "Won",
                                "metadata": {"isClosed": "true"},
                            }
                        ],
                    }
                ]
            }

            # Mock search response (POST)
            search_response = Mock()
            search_response.status_code = 200
            search_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "properties": {
                            "dealname": "Test Deal",
                            "amount": "10000",
                            "closedate": "2024-01-15",
                            "dealstage": "won-stage-id",
                        },
                    }
                ],
                "paging": {},
            }

            # Mock associations response
            assoc_response = Mock()
            assoc_response.status_code = 200
            assoc_response.json.return_value = {"results": []}

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.side_effect = [pipelines_response, assoc_response]
                mock_client.post.return_value = search_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await job._execute_job()

                assert result["status"] == "success"
                assert result["records_processed"] == 1
                assert len(result["deals"]) == 1
                assert result["deals"][0]["deal_name"] == "Test Deal"
                assert result["deals"][0]["amount"] == 10000.0

    @pytest.mark.asyncio
    async def test_execute_job_filters_closed_won_deals(self, mock_settings):
        """Test that job uses search API for won deals only."""
        job = HubSpotSyncJob(
            mock_settings,
            credential_id="test-cred",
            skip_vector_ingestion=True,
        )

        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock pipelines response
            pipelines_response = Mock()
            pipelines_response.status_code = 200
            pipelines_response.json.return_value = {
                "results": [
                    {
                        "id": "pipeline-1",
                        "label": "Pipeline",
                        "stages": [
                            {
                                "id": "won-stage",
                                "label": "Won",
                                "metadata": {"isClosed": "true"},
                            }
                        ],
                    }
                ]
            }

            # Mock search returns only Won deals (search API filters)
            search_response = Mock()
            search_response.status_code = 200
            search_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "properties": {
                            "dealname": "Won Deal",
                            "amount": "5000",
                            "dealstage": "won-stage",
                        },
                    }
                ],
                "paging": {},
            }

            assoc_response = Mock()
            assoc_response.status_code = 200
            assoc_response.json.return_value = {"results": []}

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.side_effect = [pipelines_response, assoc_response]
                mock_client.post.return_value = search_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await job._execute_job()

                assert result["records_processed"] == 1
                assert result["deals"][0]["deal_name"] == "Won Deal"

    @pytest.mark.asyncio
    async def test_execute_job_no_won_stages(self, mock_settings):
        """Test handling when no Won stages are found."""
        job = HubSpotSyncJob(
            mock_settings,
            credential_id="test-cred",
            skip_vector_ingestion=True,
        )

        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock pipelines with no Won stages
            pipelines_response = Mock()
            pipelines_response.status_code = 200
            pipelines_response.json.return_value = {
                "results": [
                    {
                        "id": "pipeline-1",
                        "label": "Pipeline",
                        "stages": [
                            {
                                "id": "open-stage",
                                "label": "Open",
                                "metadata": {"isClosed": "false"},
                            }
                        ],
                    }
                ]
            }

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = pipelines_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                result = await job._execute_job()

                # Should return empty since no Won stages found
                assert result["records_processed"] == 0
                assert len(result["deals"]) == 0


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
        assert hasattr(job, "_fetch_owner")
        assert hasattr(job, "_build_deal_document")


class TestHubSpotSyncJobOwnerFetching:
    """Test deal owner fetching from HubSpot."""

    @pytest.mark.asyncio
    async def test_fetch_owner_success(self, mock_settings):
        """Test successfully fetching owner details."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        owner_response = Mock()
        owner_response.status_code = 200
        owner_response.json.return_value = {
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@company.com",
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = owner_response

        result = await job._fetch_owner(
            mock_client, {"Authorization": "Bearer test"}, "owner-123"
        )

        assert result is not None
        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"
        assert result["email"] == "john.doe@company.com"

    @pytest.mark.asyncio
    async def test_fetch_owner_not_found(self, mock_settings):
        """Test handling of non-existent owner."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        owner_response = Mock()
        owner_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = owner_response

        result = await job._fetch_owner(mock_client, {}, "nonexistent-owner")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_owner_handles_exception(self, mock_settings):
        """Test owner fetch gracefully handles exceptions."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")

        result = await job._fetch_owner(mock_client, {}, "owner-123")

        assert result is None


class TestHubSpotSyncJobDocumentBuilding:
    """Test document building for vector storage."""

    def test_build_deal_document_complete(self, mock_settings):
        """Test building document with all fields."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        deal = {
            "deal_id": "deal-123",
            "deal_name": "Enterprise Deal",
            "amount": 150000.0,
            "close_date": "2024-03-15",
            "company_name": "Acme Corp",
            "company_domain": "acme.com",
            "industry": "Technology",
            "tech_stack": ["Python", "React", "AWS"],
            "num_employees": "500",
            "owner_name": "John Doe",
            "owner_email": "john@company.com",
            "currency": "USD",
            "source": "Referral",
            "qualified_services": "Software Development",
            "practice_studio": "Engineering",
        }

        result = job._build_deal_document(deal)

        # Check content includes all fields
        assert "Client: Acme Corp" in result["content"]
        assert "Deal Owner: John Doe" in result["content"]
        assert "Tech Stack: Python, React, AWS" in result["content"]
        assert "Currency: USD" in result["content"]
        assert "Source: Referral" in result["content"]
        assert "Qualified Services: Software Development" in result["content"]
        assert "Practice/Studio: Engineering" in result["content"]
        assert "Team Size: 500" in result["content"]
        assert "Close Date: 2024-03-15" in result["content"]
        assert "Deal ID: deal-123" in result["content"]
        assert "150,000.00" in result["content"]

        # Check metadata
        assert result["metadata"]["source"] == "hubspot"
        assert result["metadata"]["type"] == "closed_deal"
        assert result["metadata"]["deal_id"] == "deal-123"
        assert result["metadata"]["client"] == "Acme Corp"
        assert result["metadata"]["amount"] == 150000.0
        assert result["metadata"]["currency"] == "USD"
        assert result["metadata"]["deal_owner"] == "John Doe"
        assert "ingested_at" in result["metadata"]

    def test_build_deal_document_minimal(self, mock_settings):
        """Test building document with minimal fields."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        deal = {
            "deal_id": "deal-456",
            "deal_name": "Minimal Deal",
            "amount": 10000.0,
        }

        result = job._build_deal_document(deal)

        # Should handle missing fields gracefully
        assert "Client: Unknown" in result["content"]
        assert "Deal Owner: Not specified" in result["content"]
        assert "Tech Stack: Not specified" in result["content"]
        assert "Currency: USD" in result["content"]  # Default currency

        # Metadata should have defaults
        assert result["metadata"]["currency"] == "USD"
        assert result["metadata"]["tech_stack"] == []

    def test_build_deal_document_empty_tech_stack(self, mock_settings):
        """Test handling of empty tech stack."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        deal = {
            "deal_id": "deal-789",
            "deal_name": "No Tech Deal",
            "amount": 5000.0,
            "tech_stack": [],
        }

        result = job._build_deal_document(deal)

        assert "Tech Stack: Not specified" in result["content"]


class TestHubSpotSyncJobDealProperties:
    """Test deal properties configuration."""

    def test_deal_properties_includes_new_fields(self):
        """Test that DEAL_PROPERTIES includes all required fields."""
        # Core fields
        assert "dealname" in DEAL_PROPERTIES
        assert "amount" in DEAL_PROPERTIES
        assert "closedate" in DEAL_PROPERTIES
        assert "dealstage" in DEAL_PROPERTIES
        assert "pipeline" in DEAL_PROPERTIES

        # New fields for enhanced ingestion
        assert "hubspot_owner_id" in DEAL_PROPERTIES
        assert "deal_currency_code" in DEAL_PROPERTIES
        assert "hs_analytics_source" in DEAL_PROPERTIES
        assert "qualified_services" in DEAL_PROPERTIES
        assert "practice_studio__cloned_" in DEAL_PROPERTIES
        assert "deal_tech_stacks" in DEAL_PROPERTIES
        assert "tam" in DEAL_PROPERTIES
        assert "no_of_crafters_needed" in DEAL_PROPERTIES

    def test_deal_properties_includes_metric_fields(self):
        """Test that DEAL_PROPERTIES includes Metric.ai integration fields."""
        assert "metric_id" in DEAL_PROPERTIES
        assert "metric_link" in DEAL_PROPERTIES


class TestHubSpotSyncJobMetricIdHandling:
    """Test metric_id extraction and recording."""

    def test_build_deal_document_with_metric_id(self, mock_settings):
        """Test building document includes metric_id fields."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        deal = {
            "deal_id": "deal-123",
            "deal_name": "Metric-Linked Deal",
            "amount": 100000.0,
            "company_name": "Acme Corp",
            "metric_id": "70850",
            "metric_link": "https://psa.metric.ai/projects/70850/overview",
        }

        result = job._build_deal_document(deal)

        # Check content includes metric fields
        assert "Metric Project ID: 70850" in result["content"]
        assert (
            "Metric Link: https://psa.metric.ai/projects/70850/overview"
            in result["content"]
        )

        # Check metadata includes metric fields
        assert result["metadata"]["metric_id"] == "70850"
        assert (
            result["metadata"]["metric_link"]
            == "https://psa.metric.ai/projects/70850/overview"
        )

    def test_build_deal_document_without_metric_id(self, mock_settings):
        """Test building document handles missing metric_id gracefully."""
        job = HubSpotSyncJob(mock_settings, credential_id="test-cred")

        deal = {
            "deal_id": "deal-456",
            "deal_name": "No Metric Deal",
            "amount": 50000.0,
        }

        result = job._build_deal_document(deal)

        # Should show "Not linked" for missing metric fields
        assert "Metric Project ID: Not linked" in result["content"]
        assert "Metric Link: Not linked" in result["content"]

        # Metadata should have None values
        assert result["metadata"]["metric_id"] is None
        assert result["metadata"]["metric_link"] is None

    @pytest.mark.asyncio
    async def test_execute_job_passes_metric_id_to_tracking(self, mock_settings):
        """Test that metric_id is passed to record_deal_ingestion."""
        job = HubSpotSyncJob(
            mock_settings,
            credential_id="test-cred",
            limit=5,
        )

        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock pipelines response
            pipelines_response = Mock()
            pipelines_response.status_code = 200
            pipelines_response.json.return_value = {
                "results": [
                    {
                        "id": "pipeline-1",
                        "label": "New Business",
                        "stages": [
                            {
                                "id": "won-stage-id",
                                "label": "Won",
                                "metadata": {"isClosed": "true"},
                            }
                        ],
                    }
                ]
            }

            # Mock search response with metric_id
            search_response = Mock()
            search_response.status_code = 200
            search_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "updatedAt": "2024-01-15T10:00:00Z",
                        "properties": {
                            "dealname": "Metric Deal",
                            "amount": "10000",
                            "dealstage": "won-stage-id",
                            "metric_id": "70850",
                            "metric_link": "https://psa.metric.ai/projects/70850",
                        },
                    }
                ],
                "paging": {},
            }

            assoc_response = Mock()
            assoc_response.status_code = 200
            assoc_response.json.return_value = {"results": []}

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.side_effect = [pipelines_response, assoc_response]
                mock_client.post.return_value = search_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock the services
                mock_tracking = Mock()
                mock_tracking.check_deal_needs_reindex.return_value = (True, None)
                mock_tracking.generate_base_uuid.return_value = "uuid-123"

                mock_embeddings = Mock()
                mock_embeddings.embed_batch.return_value = [[0.1, 0.2, 0.3]]

                mock_qdrant = AsyncMock()
                mock_qdrant.initialize = AsyncMock()
                mock_qdrant.upsert_with_namespace = AsyncMock()
                mock_qdrant.close = AsyncMock()

                with (
                    patch(
                        "jobs.hubspot_sync.HubSpotDealTrackingService",
                        return_value=mock_tracking,
                    ),
                    patch(
                        "jobs.hubspot_sync.OpenAIEmbeddings",
                        return_value=mock_embeddings,
                    ),
                    patch("jobs.hubspot_sync.QdrantClient", return_value=mock_qdrant),
                ):
                    await job._execute_job()

                    # Verify metric_id was passed to record_deal_ingestion
                    mock_tracking.record_deal_ingestion.assert_called_once()
                    call_kwargs = mock_tracking.record_deal_ingestion.call_args.kwargs
                    assert call_kwargs["metric_id"] == "70850"


class TestHubSpotSyncJobVectorIngestion:
    """Test vector ingestion integration."""

    @pytest.mark.asyncio
    async def test_execute_job_with_skip_vector_ingestion(self, mock_settings):
        """Test job execution with skip_vector_ingestion=True."""
        job = HubSpotSyncJob(
            mock_settings,
            credential_id="test-cred",
            limit=5,
            skip_vector_ingestion=True,
        )

        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock pipelines response
            pipelines_response = Mock()
            pipelines_response.status_code = 200
            pipelines_response.json.return_value = {
                "results": [
                    {
                        "id": "pipeline-1",
                        "label": "Pipeline",
                        "stages": [
                            {
                                "id": "won-stage",
                                "label": "Won",
                                "metadata": {"isClosed": "true"},
                            }
                        ],
                    }
                ]
            }

            # Mock search response
            search_response = Mock()
            search_response.status_code = 200
            search_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "properties": {
                            "dealname": "Test Deal",
                            "amount": "10000",
                            "dealstage": "won-stage",
                        },
                    }
                ],
                "paging": {},
            }

            assoc_response = Mock()
            assoc_response.status_code = 200
            assoc_response.json.return_value = {"results": []}

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.side_effect = [pipelines_response, assoc_response]
                mock_client.post.return_value = search_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Should not try to initialize vector clients
                with (
                    patch("jobs.hubspot_sync.HubSpotDealTrackingService"),
                    patch("jobs.hubspot_sync.OpenAIEmbeddings") as mock_embeddings,
                    patch("jobs.hubspot_sync.QdrantClient") as mock_qdrant,
                ):
                    result = await job._execute_job()

                    # Vector clients should not be initialized
                    mock_embeddings.assert_not_called()
                    mock_qdrant.assert_not_called()

                    assert result["status"] == "success"
                    assert result["records_processed"] == 1

    @pytest.mark.asyncio
    async def test_execute_job_with_vector_ingestion(self, mock_settings):
        """Test job execution with vector ingestion enabled."""
        job = HubSpotSyncJob(
            mock_settings,
            credential_id="test-cred",
            limit=5,
            skip_vector_ingestion=False,
        )

        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock pipelines response
            pipelines_response = Mock()
            pipelines_response.status_code = 200
            pipelines_response.json.return_value = {
                "results": [
                    {
                        "id": "pipeline-1",
                        "label": "New Business",
                        "stages": [
                            {
                                "id": "won-stage-id",
                                "label": "Won",
                                "metadata": {"isClosed": "true"},
                            }
                        ],
                    }
                ]
            }

            # Mock search response (POST)
            search_response = Mock()
            search_response.status_code = 200
            search_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "updatedAt": "2024-01-15T10:00:00Z",
                        "properties": {
                            "dealname": "Test Deal",
                            "amount": "10000",
                            "dealstage": "won-stage-id",
                            "hubspot_owner_id": "owner-1",
                        },
                    }
                ],
                "paging": {},
            }

            # Mock associations response
            assoc_response = Mock()
            assoc_response.status_code = 200
            assoc_response.json.return_value = {"results": []}

            # Mock owner response
            owner_response = Mock()
            owner_response.status_code = 200
            owner_response.json.return_value = {
                "firstName": "John",
                "lastName": "Doe",
                "email": "john@example.com",
            }

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                # GET: pipelines, associations, owner
                mock_client.get.side_effect = [
                    pipelines_response,
                    assoc_response,
                    owner_response,
                ]
                # POST: search
                mock_client.post.return_value = search_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock the services
                mock_tracking = Mock()
                mock_tracking.check_deal_needs_reindex.return_value = (
                    True,
                    None,
                )  # Needs indexing
                mock_tracking.generate_base_uuid.return_value = "uuid-123"

                mock_embeddings = Mock()
                mock_embeddings.embed_batch.return_value = [[0.1, 0.2, 0.3]]

                mock_qdrant = AsyncMock()
                mock_qdrant.initialize = AsyncMock()
                mock_qdrant.upsert_with_namespace = AsyncMock()
                mock_qdrant.close = AsyncMock()

                with (
                    patch(
                        "jobs.hubspot_sync.HubSpotDealTrackingService",
                        return_value=mock_tracking,
                    ),
                    patch(
                        "jobs.hubspot_sync.OpenAIEmbeddings",
                        return_value=mock_embeddings,
                    ),
                    patch("jobs.hubspot_sync.QdrantClient", return_value=mock_qdrant),
                ):
                    result = await job._execute_job()

                    # Vector clients should be initialized
                    mock_qdrant.initialize.assert_called_once()

                    # Should have indexed the deal
                    assert result["records_indexed"] == 1

                    # Should have called upsert
                    mock_qdrant.upsert_with_namespace.assert_called_once()

                    # Should have recorded the ingestion
                    mock_tracking.record_deal_ingestion.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_job_skips_unchanged_deals(self, mock_settings):
        """Test that unchanged deals are skipped during vector ingestion."""
        job = HubSpotSyncJob(
            mock_settings,
            credential_id="test-cred",
            limit=5,
        )

        with patch.object(job, "_load_credentials", return_value="test-token"):
            # Mock pipelines response
            pipelines_response = Mock()
            pipelines_response.status_code = 200
            pipelines_response.json.return_value = {
                "results": [
                    {
                        "id": "pipeline-1",
                        "label": "New Business",
                        "stages": [
                            {
                                "id": "won-stage-id",
                                "label": "Won",
                                "metadata": {"isClosed": "true"},
                            }
                        ],
                    }
                ]
            }

            # Mock search response (POST)
            search_response = Mock()
            search_response.status_code = 200
            search_response.json.return_value = {
                "results": [
                    {
                        "id": "deal-1",
                        "properties": {
                            "dealname": "Unchanged Deal",
                            "amount": "10000",
                            "dealstage": "won-stage-id",
                        },
                    }
                ],
                "paging": {},
            }

            # Mock associations response
            assoc_response = Mock()
            assoc_response.status_code = 200
            assoc_response.json.return_value = {"results": []}

            with patch("jobs.hubspot_sync.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.side_effect = [pipelines_response, assoc_response]
                mock_client.post.return_value = search_response
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock tracking to say deal doesn't need reindexing
                mock_tracking = Mock()
                mock_tracking.check_deal_needs_reindex.return_value = (
                    False,
                    "existing-uuid",
                )

                mock_embeddings = Mock()
                mock_qdrant = AsyncMock()
                mock_qdrant.initialize = AsyncMock()
                mock_qdrant.close = AsyncMock()

                with (
                    patch(
                        "jobs.hubspot_sync.HubSpotDealTrackingService",
                        return_value=mock_tracking,
                    ),
                    patch(
                        "jobs.hubspot_sync.OpenAIEmbeddings",
                        return_value=mock_embeddings,
                    ),
                    patch("jobs.hubspot_sync.QdrantClient", return_value=mock_qdrant),
                ):
                    result = await job._execute_job()

                    # Deal was processed but skipped for indexing
                    assert result["records_processed"] == 1
                    assert result["records_skipped_unchanged"] == 1
                    assert result["records_indexed"] == 0

                    # Should not have called embed or upsert
                    mock_embeddings.embed_batch.assert_not_called()
                    mock_qdrant.upsert_with_namespace.assert_not_called()

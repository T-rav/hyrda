"""Tests for Metric.ai sync job."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config.settings import TasksSettings
from jobs.metric_sync import MetricSyncJob


@pytest.fixture
def mock_metric_client():
    """Mock Metric.ai client."""
    with patch("jobs.metric_sync.MetricClient") as mock:
        client = MagicMock()
        mock.return_value = client

        # Mock employees data
        client.get_employees.return_value = [
            {
                "id": "emp1",
                "name": "John Doe",
                "email": "john@example.com",
                "startedWorking": "2020-01-01",
                "endedWorking": None,
                "groups": [
                    {"name": "Engineer", "groupType": "GROUP_TYPE_11"},
                    {"name": "Engineering", "groupType": "DEPARTMENT"},
                    {"name": "Backend", "groupType": "GROUP_TYPE_23"},
                ],
            }
        ]

        # Mock clients data
        client.get_clients.return_value = [{"id": "client1", "name": "Acme Corp"}]

        # Mock projects data
        client.get_projects.return_value = [
            {
                "id": "proj1",
                "name": "Project Alpha",
                "projectType": "BILLABLE",
                "projectStatus": "ACTIVE",
                "startDate": "2024-01-01",
                "endDate": "2024-12-31",
                "groups": [
                    {"id": "client1", "name": "Acme Corp", "groupType": "CLIENT"},
                    {
                        "id": "owner1",
                        "name": "Jane Smith",
                        "groupType": "GROUP_TYPE_12",
                    },
                    {"id": "freq1", "name": "Monthly", "groupType": "GROUP_TYPE_7"},
                ],
            }
        ]

        # Mock allocations data
        client.get_allocations.return_value = [
            {
                "id": "alloc1",
                "startDate": "2024-01-01",
                "endDate": "2024-12-31",
                "employee": {"id": "emp1", "name": "John Doe"},
                "project": {"id": "proj1", "name": "Project Alpha"},
            }
        ]

        yield client


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    store.add_documents = AsyncMock()
    store.close = AsyncMock()
    store.index = MagicMock()  # Simulate Pinecone
    return store


@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider."""
    provider = MagicMock()
    provider.embed_batch.return_value = [[0.1, 0.2, 0.3]]
    return provider


@pytest.fixture
def settings():
    """Create test settings."""
    return TasksSettings()


@pytest.mark.asyncio
async def test_sync_employees(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test employee sync."""
    with (
        patch("jobs.metric_sync.create_vector_store", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.create_embedding_provider",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=True,
            sync_projects=False,
            sync_clients=False,
            sync_allocations=False,
        )

        result = await job._execute_job()

        assert result["employees_synced"] == 1
        assert result["projects_synced"] == 0
        assert result["clients_synced"] == 0
        assert result["allocations_synced"] == 0
        assert mock_vector_store.initialize.called
        assert mock_embedding_provider.embed_batch.called


@pytest.mark.asyncio
async def test_sync_projects(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test project sync."""
    with (
        patch("jobs.metric_sync.create_vector_store", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.create_embedding_provider",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=True,
            sync_clients=False,
            sync_allocations=False,
        )

        result = await job._execute_job()

        assert result["projects_synced"] == 1
        assert mock_embedding_provider.embed_batch.called


@pytest.mark.asyncio
async def test_sync_clients(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test client sync."""
    with (
        patch("jobs.metric_sync.create_vector_store", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.create_embedding_provider",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=False,
            sync_clients=True,
            sync_allocations=False,
        )

        result = await job._execute_job()

        assert result["clients_synced"] == 1


@pytest.mark.asyncio
async def test_sync_allocations(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test allocation sync."""
    with (
        patch("jobs.metric_sync.create_vector_store", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.create_embedding_provider",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=False,
            sync_clients=False,
            sync_allocations=True,
            allocations_start_year=2024,
        )

        result = await job._execute_job()

        assert result["allocations_synced"] == 1


@pytest.mark.asyncio
async def test_sync_all_data_types(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test syncing all data types."""
    with (
        patch("jobs.metric_sync.create_vector_store", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.create_embedding_provider",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(settings)

        result = await job._execute_job()

        assert result["employees_synced"] == 1
        assert result["projects_synced"] == 1
        assert result["clients_synced"] == 1
        assert result["allocations_synced"] == 1
        assert mock_vector_store.close.called


@pytest.mark.asyncio
async def test_employee_metadata_structure(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that employee metadata has correct structure."""
    with (
        patch("jobs.metric_sync.create_vector_store", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.create_embedding_provider",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=True,
            sync_projects=False,
            sync_clients=False,
            sync_allocations=False,
        )

        await job._execute_job()

        # Check that add_documents was called with correct structure
        call_args = mock_embedding_provider.embed_batch.call_args
        texts = call_args[0][0]

        # Verify text contains expected fields
        assert "Employee: John Doe" in texts[0]
        assert "Role: Engineer" in texts[0]
        assert "Department: Engineering" in texts[0]
        assert "Practice: Backend" in texts[0]


@pytest.mark.asyncio
async def test_project_filtering(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that non-billable projects are filtered out."""
    # Add non-billable project to mock data
    mock_metric_client.get_projects.return_value.append(
        {
            "id": "proj2",
            "name": "Internal Project",
            "projectType": "INTERNAL",
            "projectStatus": "ACTIVE",
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "groups": [
                {"id": "client1", "name": "Acme Corp", "groupType": "CLIENT"},
            ],
        }
    )

    with (
        patch("jobs.metric_sync.create_vector_store", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.create_embedding_provider",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=True,
            sync_clients=False,
            sync_allocations=False,
        )

        result = await job._execute_job()

        # Only 1 billable project should be synced
        assert result["projects_synced"] == 1


def test_job_metadata():
    """Test job metadata is correct."""
    assert MetricSyncJob.JOB_NAME == "Metric.ai Data Sync"
    assert "employees" in MetricSyncJob.JOB_DESCRIPTION.lower()
    assert "sync_employees" in MetricSyncJob.OPTIONAL_PARAMS
    assert "sync_projects" in MetricSyncJob.OPTIONAL_PARAMS
    assert "sync_clients" in MetricSyncJob.OPTIONAL_PARAMS
    assert "sync_allocations" in MetricSyncJob.OPTIONAL_PARAMS

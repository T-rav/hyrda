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
                    {"name": "Senior Software Engineer", "groupType": "ROLE"},
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
    store.index = MagicMock()  # Simulate Qdrant
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
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=True,
            sync_projects=False,
            sync_clients=False,
        )

        result = await job._execute_job()

        assert result["employees_synced"] == 1
        assert result["projects_synced"] == 0
        assert result["clients_synced"] == 0
        assert mock_vector_store.initialize.called
        assert mock_embedding_provider.embed_batch.called


@pytest.mark.asyncio
async def test_sync_projects(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test project sync."""
    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=True,
            sync_clients=False,
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
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=False,
            sync_clients=True,
        )

        result = await job._execute_job()

        assert result["clients_synced"] == 1


@pytest.mark.asyncio
async def test_sync_all_data_types(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test syncing all data types."""
    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(settings)

        result = await job._execute_job()

        assert result["employees_synced"] == 1
        assert result["projects_synced"] == 1
        assert result["clients_synced"] == 1
        assert mock_vector_store.close.called


@pytest.mark.asyncio
async def test_employee_metadata_structure(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that employee metadata has correct structure."""
    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=True,
            sync_projects=False,
            sync_clients=False,
        )

        await job._execute_job()

        # Check that add_documents was called with correct structure
        call_args = mock_embedding_provider.embed_batch.call_args
        texts = call_args[0][0]

        # Verify text contains expected fields
        assert "Employee: John Doe" in texts[0]
        assert "Title: Senior Software Engineer" in texts[0]
        assert "Email: john@example.com" in texts[0]
        assert "Status: Allocated" in texts[0]
        assert "Started: 2020-01-01" in texts[0]


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
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=True,
            sync_clients=False,
        )

        result = await job._execute_job()

        # Only 1 billable project should be synced
        assert result["projects_synced"] == 1


@pytest.mark.asyncio
async def test_database_writes_for_employees(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that _write_metric_records is called with correct employee data."""
    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=True,
            sync_projects=False,
            sync_clients=False,
        )

        # Mock the database write method
        with patch.object(job, "_write_metric_records") as mock_db_write:
            mock_db_write.return_value = 1  # Return count of records written

            await job._execute_job()

            # Verify _write_metric_records was called once for employees
            assert mock_db_write.call_count == 1

            # Get the call arguments
            call_args = mock_db_write.call_args[0][0]

            # Verify the structure of database records
            assert len(call_args) == 1
            record = call_args[0]
            assert record["metric_id"] == "emp1"
            assert record["data_type"] == "employee"
            assert record["vector_id"] == "metric_employee_emp1"
            assert record["vector_namespace"] == "metric"
            assert "Employee: John Doe" in record["content_snapshot"]


@pytest.mark.asyncio
async def test_database_writes_for_projects(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that _write_metric_records is called with correct project data."""
    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=True,
            sync_clients=False,
        )

        with patch.object(job, "_write_metric_records") as mock_db_write:
            mock_db_write.return_value = 1

            await job._execute_job()

            assert mock_db_write.call_count == 1

            call_args = mock_db_write.call_args[0][0]
            record = call_args[0]
            assert record["metric_id"] == "proj1"
            assert record["data_type"] == "project"
            assert record["vector_id"] == "metric_project_proj1"
            assert "Project: Project Alpha" in record["content_snapshot"]


@pytest.mark.asyncio
async def test_database_writes_for_clients(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that _write_metric_records is called with correct client data."""
    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=False,
            sync_clients=True,
        )

        with patch.object(job, "_write_metric_records") as mock_db_write:
            mock_db_write.return_value = 1

            await job._execute_job()

            assert mock_db_write.call_count == 1

            call_args = mock_db_write.call_args[0][0]
            record = call_args[0]
            assert record["metric_id"] == "client1"
            assert record["data_type"] == "client"
            assert record["vector_id"] == "metric_client_client1"
            assert "Client: Acme Corp" in record["content_snapshot"]


@pytest.mark.asyncio
async def test_database_write_failure_does_not_block_sync(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that database write failures don't prevent Qdrant sync."""
    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=True,
            sync_projects=False,
            sync_clients=False,
        )

        with patch.object(job, "_write_metric_records") as mock_db_write:
            # Simulate database write failure
            mock_db_write.return_value = 0

            result = await job._execute_job()

            # Qdrant sync should still succeed
            assert result["employees_synced"] == 1
            assert mock_vector_store.initialize.called


@pytest.mark.asyncio
async def test_employee_project_history(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that employee records include project history from allocations."""
    # Mock allocations for project history
    mock_metric_client.get_allocations.return_value = [
        {
            "id": "alloc1",
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "employee": {"id": "emp1", "name": "John Doe"},
            "project": {"id": "proj1", "name": "Project Alpha"},
        },
        {
            "id": "alloc2",
            "startDate": "2023-01-01",
            "endDate": "2023-12-31",
            "employee": {"id": "emp1", "name": "John Doe"},
            "project": {"id": "proj2", "name": "Project Beta"},
        },
    ]

    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=True,
            sync_projects=False,
            sync_clients=False,
            allocations_start_year=2023,
        )

        await job._execute_job()

        # Check that employee text includes project history
        call_args = mock_embedding_provider.embed_batch.call_args
        texts = call_args[0][0]
        employee_text = texts[0]

        assert "Project History:" in employee_text
        assert "Project Alpha" in employee_text or "Project Beta" in employee_text


@pytest.mark.asyncio
async def test_project_practice_field_group_type_21(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that project practice field uses GROUP_TYPE_21 (not GROUP_TYPE_23)."""
    # Mock project with GROUP_TYPE_21 for practice
    mock_metric_client.get_projects.return_value = [
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
                    "id": "practice1",
                    "name": "Marketplace Engineering",
                    "groupType": "GROUP_TYPE_21",
                },
                {"id": "owner1", "name": "Jane Smith", "groupType": "GROUP_TYPE_12"},
                {"id": "freq1", "name": "Monthly", "groupType": "GROUP_TYPE_7"},
            ],
        }
    ]

    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=True,
            sync_clients=False,
        )

        await job._execute_job()

        # Check that project text includes practice field
        call_args = mock_embedding_provider.embed_batch.call_args
        texts = call_args[0][0]
        project_text = texts[0]

        assert "Practice: Marketplace Engineering" in project_text


@pytest.mark.asyncio
async def test_project_practice_field_defaults_to_unknown(
    settings, mock_metric_client, mock_vector_store, mock_embedding_provider
):
    """Test that project practice field defaults to 'Unknown' when GROUP_TYPE_21 is missing."""
    # Mock project without GROUP_TYPE_21
    mock_metric_client.get_projects.return_value = [
        {
            "id": "proj1",
            "name": "Project Alpha",
            "projectType": "BILLABLE",
            "projectStatus": "ACTIVE",
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "groups": [
                {"id": "client1", "name": "Acme Corp", "groupType": "CLIENT"},
                {"id": "owner1", "name": "Jane Smith", "groupType": "GROUP_TYPE_12"},
            ],
        }
    ]

    with (
        patch("jobs.metric_sync.QdrantClient", return_value=mock_vector_store),
        patch(
            "jobs.metric_sync.OpenAIEmbeddings",
            return_value=mock_embedding_provider,
        ),
    ):
        job = MetricSyncJob(
            settings,
            sync_employees=False,
            sync_projects=True,
            sync_clients=False,
        )

        await job._execute_job()

        # Check that project text shows Unknown practice
        call_args = mock_embedding_provider.embed_batch.call_args
        texts = call_args[0][0]
        project_text = texts[0]

        assert "Practice: Unknown" in project_text


def test_job_metadata():
    """Test job metadata is correct."""
    assert MetricSyncJob.JOB_NAME == "Metric.ai Data Sync"
    assert "employees" in MetricSyncJob.JOB_DESCRIPTION.lower()
    assert "sync_employees" in MetricSyncJob.OPTIONAL_PARAMS
    assert "sync_projects" in MetricSyncJob.OPTIONAL_PARAMS
    assert "sync_clients" in MetricSyncJob.OPTIONAL_PARAMS

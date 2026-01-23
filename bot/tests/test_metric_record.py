"""Tests for models/metric_record.py"""

from models.metric_record import MetricRecord


class TestMetricRecord:
    """Tests for MetricRecord model."""

    def test_metric_record_creation(self):
        """Test creating a MetricRecord instance."""
        record = MetricRecord(
            metric_id="emp_123",
            data_type="employee",
            pinecone_id="metric_emp_123",
            pinecone_namespace="metric",
            content_snapshot="John Doe - Software Engineer",
        )

        assert record.metric_id == "emp_123"
        assert record.data_type == "employee"
        assert record.pinecone_id == "metric_emp_123"
        assert record.pinecone_namespace == "metric"
        assert record.content_snapshot == "John Doe - Software Engineer"

    def test_metric_record_repr(self):
        """Test MetricRecord __repr__ method."""
        record = MetricRecord(
            id=42,
            metric_id="emp_123",
            data_type="employee",
            pinecone_id="metric_emp_123",
            content_snapshot="Test content",
        )

        repr_str = repr(record)

        assert "MetricRecord" in repr_str
        assert "id=42" in repr_str
        assert "metric_id=emp_123" in repr_str
        assert "data_type=employee" in repr_str

    def test_metric_record_with_explicit_namespace(self):
        """Test MetricRecord with explicit namespace."""
        record = MetricRecord(
            metric_id="proj_456",
            data_type="project",
            pinecone_id="metric_proj_456",
            pinecone_namespace="custom_namespace",
            content_snapshot="Project XYZ",
        )

        assert record.pinecone_namespace == "custom_namespace"

    def test_metric_record_timestamps(self):
        """Test MetricRecord timestamp handling."""
        record = MetricRecord(
            metric_id="client_789",
            data_type="client",
            pinecone_id="metric_client_789",
            content_snapshot="Acme Corp",
        )

        # Timestamps start as None until persisted
        assert record.created_at is None
        assert record.updated_at is None
        assert record.synced_at is None

    def test_metric_record_all_data_types(self):
        """Test MetricRecord with different data types."""
        data_types = ["employee", "project", "client", "allocation"]

        for idx, data_type in enumerate(data_types):
            record = MetricRecord(
                metric_id=f"{data_type}_{idx}",
                data_type=data_type,
                pinecone_id=f"metric_{data_type}_{idx}",
                content_snapshot=f"Test {data_type} content",
            )

            assert record.data_type == data_type
            assert record.metric_id == f"{data_type}_{idx}"

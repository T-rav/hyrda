"""Tests for HubSpot deal tracking service (services/hubspot_deal_tracking_service.py).

Tests focus on hash computation, UUID generation, change detection, and database operations.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

from services.hubspot_deal_tracking_service import HubSpotDealTrackingService


class TestDealHashComputation:
    """Test deal hash computation for change detection."""

    def test_compute_deal_hash_deterministic(self):
        """Test that same deal data produces same hash."""
        service = HubSpotDealTrackingService()

        deal_data = {
            "deal_id": "123",
            "deal_name": "Test Deal",
            "amount": 50000.0,
            "close_date": "2024-01-15",
            "company_name": "Acme Corp",
            "tech_stack": ["Python", "React"],
        }

        hash1 = service.compute_deal_hash(deal_data)
        hash2 = service.compute_deal_hash(deal_data)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_compute_deal_hash_different_for_changed_data(self):
        """Test that different deal data produces different hashes."""
        service = HubSpotDealTrackingService()

        deal_data_v1 = {
            "deal_id": "123",
            "deal_name": "Test Deal",
            "amount": 50000.0,
            "company_name": "Acme Corp",
        }

        deal_data_v2 = {
            "deal_id": "123",
            "deal_name": "Test Deal",
            "amount": 75000.0,  # Amount changed
            "company_name": "Acme Corp",
        }

        hash1 = service.compute_deal_hash(deal_data_v1)
        hash2 = service.compute_deal_hash(deal_data_v2)

        assert hash1 != hash2

    def test_compute_deal_hash_tech_stack_order_independent(self):
        """Test that tech stack order doesn't affect hash (sorted)."""
        service = HubSpotDealTrackingService()

        deal_data_v1 = {
            "deal_id": "123",
            "tech_stack": ["Python", "React", "AWS"],
        }

        deal_data_v2 = {
            "deal_id": "123",
            "tech_stack": ["AWS", "Python", "React"],  # Different order
        }

        hash1 = service.compute_deal_hash(deal_data_v1)
        hash2 = service.compute_deal_hash(deal_data_v2)

        # Should be same because tech_stack is sorted
        assert hash1 == hash2

    def test_compute_deal_hash_handles_missing_fields(self):
        """Test hash computation with missing optional fields."""
        service = HubSpotDealTrackingService()

        deal_data = {
            "deal_id": "123",
            "deal_name": "Test Deal",
            # Missing many optional fields
        }

        # Should not raise
        hash_value = service.compute_deal_hash(deal_data)
        assert len(hash_value) == 64

    def test_compute_deal_hash_includes_new_fields(self):
        """Test that new fields (owner, currency, etc.) affect hash."""
        service = HubSpotDealTrackingService()

        deal_data_v1 = {
            "deal_id": "123",
            "deal_name": "Test Deal",
            "owner_name": "John Doe",
        }

        deal_data_v2 = {
            "deal_id": "123",
            "deal_name": "Test Deal",
            "owner_name": "Jane Smith",  # Owner changed
        }

        hash1 = service.compute_deal_hash(deal_data_v1)
        hash2 = service.compute_deal_hash(deal_data_v2)

        assert hash1 != hash2


class TestUUIDGeneration:
    """Test deterministic UUID generation for deals."""

    def test_generate_base_uuid_deterministic(self):
        """Test that same deal ID produces same UUID."""
        uuid1 = HubSpotDealTrackingService.generate_base_uuid("deal-123")
        uuid2 = HubSpotDealTrackingService.generate_base_uuid("deal-123")

        assert uuid1 == uuid2
        # Validate UUID format
        assert len(uuid1) == 36
        assert uuid1.count("-") == 4

    def test_generate_base_uuid_different_for_different_deals(self):
        """Test that different deal IDs produce different UUIDs."""
        uuid1 = HubSpotDealTrackingService.generate_base_uuid("deal-123")
        uuid2 = HubSpotDealTrackingService.generate_base_uuid("deal-456")

        assert uuid1 != uuid2

    def test_generate_base_uuid_is_valid_uuid(self):
        """Test that generated UUID is a valid UUID5."""
        import uuid as uuid_module

        uuid_str = HubSpotDealTrackingService.generate_base_uuid("test-deal")

        # Should parse without error
        parsed = uuid_module.UUID(uuid_str)
        assert parsed.version == 5  # UUID5


class TestDealChangeDetection:
    """Test deal change detection logic."""

    def test_check_deal_needs_reindex_new_deal(self):
        """Test that new deals need indexing."""
        service = HubSpotDealTrackingService()

        deal_data = {"deal_id": "new-deal", "deal_name": "New Deal"}

        # Mock database query returning None (deal not found)
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            needs_reindex, existing_uuid = service.check_deal_needs_reindex(
                "new-deal", deal_data
            )

        assert needs_reindex is True
        assert existing_uuid is None

    def test_check_deal_needs_reindex_unchanged_deal(self):
        """Test that unchanged deals are skipped."""
        service = HubSpotDealTrackingService()

        deal_data = {"deal_id": "123", "deal_name": "Existing Deal", "amount": 50000.0}

        # Compute expected hash
        expected_hash = service.compute_deal_hash(deal_data)

        # Mock existing record with same hash
        mock_existing = Mock()
        mock_existing.deal_data_hash = expected_hash
        mock_existing.vector_uuid = "existing-uuid-123"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_existing
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            needs_reindex, existing_uuid = service.check_deal_needs_reindex(
                "123", deal_data
            )

        assert needs_reindex is False
        assert existing_uuid == "existing-uuid-123"

    def test_check_deal_needs_reindex_changed_deal(self):
        """Test that changed deals need re-indexing."""
        service = HubSpotDealTrackingService()

        deal_data = {"deal_id": "123", "deal_name": "Existing Deal", "amount": 75000.0}

        # Mock existing record with different hash
        mock_existing = Mock()
        mock_existing.deal_data_hash = "old-hash-different"
        mock_existing.vector_uuid = "existing-uuid-123"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_existing
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            needs_reindex, existing_uuid = service.check_deal_needs_reindex(
                "123", deal_data
            )

        assert needs_reindex is True
        assert existing_uuid == "existing-uuid-123"


class TestRecordDealIngestion:
    """Test recording deal ingestion in database."""

    def test_record_new_deal_ingestion(self):
        """Test recording a new deal ingestion."""
        service = HubSpotDealTrackingService()

        deal_data = {"deal_id": "123", "deal_name": "Test Deal", "amount": 50000.0}

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None  # Not existing
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            service.record_deal_ingestion(
                hubspot_deal_id="123",
                deal_name="Test Deal",
                deal_data=deal_data,
                vector_uuid="uuid-123",
                status="success",
            )

        # Verify new record was added
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_record_existing_deal_ingestion_updates(self):
        """Test that recording existing deal updates the record."""
        service = HubSpotDealTrackingService()

        deal_data = {"deal_id": "123", "deal_name": "Updated Deal", "amount": 75000.0}

        # Mock existing record
        mock_existing = Mock()
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_existing
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            service.record_deal_ingestion(
                hubspot_deal_id="123",
                deal_name="Updated Deal",
                deal_data=deal_data,
                vector_uuid="uuid-123",
                status="success",
            )

        # Verify record was updated, not added
        mock_session.add.assert_not_called()
        assert mock_existing.deal_name == "Updated Deal"
        mock_session.commit.assert_called_once()

    def test_record_deal_ingestion_with_error(self):
        """Test recording a failed deal ingestion."""
        service = HubSpotDealTrackingService()

        deal_data = {"deal_id": "123", "deal_name": "Failed Deal"}

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            service.record_deal_ingestion(
                hubspot_deal_id="123",
                deal_name="Failed Deal",
                deal_data=deal_data,
                vector_uuid="uuid-123",
                status="failed",
                error_message="API error occurred",
            )

        # Verify new record was added with error status
        mock_session.add.assert_called_once()
        added_record = mock_session.add.call_args[0][0]
        assert added_record.ingestion_status == "failed"
        assert added_record.error_message == "API error occurred"


class TestGetDealByHubspotId:
    """Test retrieving deal by HubSpot ID."""

    def test_get_deal_by_hubspot_id_found(self):
        """Test retrieving an existing deal."""
        service = HubSpotDealTrackingService()

        mock_deal = Mock()
        mock_deal.hubspot_deal_id = "123"
        mock_deal.deal_name = "Test Deal"
        mock_deal.deal_data_hash = "abc123"
        mock_deal.vector_uuid = "uuid-123"
        mock_deal.chunk_count = 1
        mock_deal.hubspot_updated_at = datetime(2024, 1, 15, tzinfo=UTC)
        mock_deal.first_ingested_at = datetime(2024, 1, 10, tzinfo=UTC)
        mock_deal.last_ingested_at = datetime(2024, 1, 15, tzinfo=UTC)
        mock_deal.ingestion_status = "success"
        mock_deal.error_message = None
        mock_deal.extra_metadata = {"key": "value"}

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_deal
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            result = service.get_deal_by_hubspot_id("123")

        assert result is not None
        assert result["hubspot_deal_id"] == "123"
        assert result["deal_name"] == "Test Deal"
        assert result["ingestion_status"] == "success"

    def test_get_deal_by_hubspot_id_not_found(self):
        """Test retrieving a non-existent deal."""
        service = HubSpotDealTrackingService()

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            result = service.get_deal_by_hubspot_id("nonexistent")

        assert result is None


class TestMarkDealRemoved:
    """Test marking deals as removed."""

    def test_mark_deal_removed_success(self):
        """Test successfully marking a deal as removed."""
        service = HubSpotDealTrackingService()

        mock_deal = Mock()
        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_deal
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            result = service.mark_deal_removed("123")

        assert result is True
        assert mock_deal.ingestion_status == "removed"
        mock_session.commit.assert_called_once()

    def test_mark_deal_removed_not_found(self):
        """Test marking non-existent deal as removed."""
        service = HubSpotDealTrackingService()

        mock_session = Mock()
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            result = service.mark_deal_removed("nonexistent")

        assert result is False
        mock_session.commit.assert_not_called()


class TestGetAllSyncedDeals:
    """Test retrieving all synced deals."""

    def test_get_all_synced_deals(self):
        """Test retrieving all synced deals."""
        service = HubSpotDealTrackingService()

        mock_deal1 = Mock()
        mock_deal1.hubspot_deal_id = "123"
        mock_deal1.deal_name = "Deal 1"
        mock_deal1.deal_data_hash = "abc123defghijklmnop"
        mock_deal1.vector_uuid = "uuid-1"
        mock_deal1.last_ingested_at = datetime(2024, 1, 15, tzinfo=UTC)
        mock_deal1.ingestion_status = "success"

        mock_deal2 = Mock()
        mock_deal2.hubspot_deal_id = "456"
        mock_deal2.deal_name = "Deal 2"
        mock_deal2.deal_data_hash = "xyz789abcdefghijklm"
        mock_deal2.vector_uuid = "uuid-2"
        mock_deal2.last_ingested_at = datetime(2024, 1, 14, tzinfo=UTC)
        mock_deal2.ingestion_status = "success"

        mock_session = Mock()
        mock_query = Mock()
        mock_query.order_by.return_value.all.return_value = [mock_deal1, mock_deal2]
        mock_session.query.return_value = mock_query

        with patch(
            "services.hubspot_deal_tracking_service.get_db_session"
        ) as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            result = service.get_all_synced_deals()

        assert len(result) == 2
        assert result[0]["hubspot_deal_id"] == "123"
        assert result[1]["hubspot_deal_id"] == "456"
        # Hash should be shortened for display
        assert len(result[0]["deal_data_hash"]) == 16

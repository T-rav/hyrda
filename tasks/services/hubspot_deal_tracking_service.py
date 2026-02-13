"""
HubSpot Deal Tracking Service

Handles tracking of synced HubSpot deals for idempotent ingestion.
Uses the hubspot_deals_data table to store content hashes and prevent duplicate indexing.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from models.base import get_data_db_session
from models.hubspot_deal_tracking import HubSpotDealTracking


class HubSpotDealTrackingService:
    """Service for tracking HubSpot deal syncing and ingestion."""

    # Namespace UUID for deterministic UUID generation (HubSpot namespace)
    NAMESPACE_UUID = uuid.UUID("a3d5e7f9-1b2c-4d5e-8f9a-0b1c2d3e4f5a")

    @staticmethod
    def compute_deal_hash(deal_data: dict[str, Any]) -> str:
        """
        Compute SHA-256 hash of deal data for change detection.

        Extracts relevant fields that would affect the document content,
        normalizes them, and computes a hash.

        Args:
            deal_data: Dictionary containing deal properties and associated data

        Returns:
            SHA-256 hash as hex string
        """
        # Extract fields that affect the document content
        relevant_fields = {
            "deal_id": deal_data.get("deal_id"),
            "deal_name": deal_data.get("deal_name"),
            "amount": deal_data.get("amount"),
            "close_date": deal_data.get("close_date"),
            "deal_stage": deal_data.get("deal_stage"),
            "company_name": deal_data.get("company_name"),
            "company_domain": deal_data.get("company_domain"),
            "industry": deal_data.get("industry"),
            "tech_stack": sorted(deal_data.get("tech_stack", [])),
            "num_employees": deal_data.get("num_employees"),
            # New fields
            "owner_name": deal_data.get("owner_name"),
            "currency": deal_data.get("currency"),
            "source": deal_data.get("source"),
            "qualified_services": deal_data.get("qualified_services"),
            "practice_studio": deal_data.get("practice_studio"),
        }

        # Serialize to JSON with sorted keys for consistency
        serialized = json.dumps(relevant_fields, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def generate_base_uuid(cls, deal_id: str) -> str:
        """
        Generate a deterministic base UUID from HubSpot deal ID.

        This UUID is used as the vector point ID in Qdrant.
        Using UUID5 ensures the same deal always gets the same UUID.

        Args:
            deal_id: HubSpot deal ID

        Returns:
            UUID string
        """
        return str(uuid.uuid5(cls.NAMESPACE_UUID, f"hubspot_deal_{deal_id}"))

    def check_deal_needs_reindex(
        self, deal_id: str, deal_data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """
        Check if a deal needs to be re-indexed based on content hash.

        Args:
            deal_id: HubSpot deal ID
            deal_data: Current deal data (enriched with company info)

        Returns:
            Tuple of (needs_reindex, existing_vector_uuid)
            - needs_reindex: True if deal is new or content changed
            - existing_vector_uuid: Existing UUID if deal was previously synced, None otherwise
        """
        new_hash = self.compute_deal_hash(deal_data)

        with get_data_db_session() as session:
            existing = (
                session.query(HubSpotDealTracking)
                .filter_by(hubspot_deal_id=deal_id)
                .first()
            )

            if not existing:
                # Deal never synced before
                return True, None

            if existing.deal_data_hash != new_hash:
                # Content changed, needs re-indexing
                return True, existing.vector_uuid

            # Content unchanged, skip re-indexing
            return False, existing.vector_uuid

    def record_deal_ingestion(
        self,
        hubspot_deal_id: str,
        deal_name: str | None,
        deal_data: dict[str, Any],
        vector_uuid: str,
        document_content: str | None = None,
        chunk_count: int = 1,
        hubspot_updated_at: datetime | None = None,
        status: str = "success",
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
        metric_id: str | None = None,
    ) -> None:
        """
        Record or update deal ingestion in the tracking table.

        Args:
            hubspot_deal_id: HubSpot deal ID
            deal_name: Deal name
            deal_data: Full deal data for hash computation
            vector_uuid: UUID used for Qdrant point ID
            document_content: Full text content stored for retrieval
            chunk_count: Number of chunks created (usually 1 for deals)
            hubspot_updated_at: Last updated timestamp from HubSpot
            status: Ingestion status (success, failed, removed)
            error_message: Error message if ingestion failed
            metadata: Additional metadata to store
            metric_id: Metric.ai project ID for direct linking
        """
        deal_hash = self.compute_deal_hash(deal_data)

        with get_data_db_session() as session:
            existing = (
                session.query(HubSpotDealTracking)
                .filter_by(hubspot_deal_id=hubspot_deal_id)
                .first()
            )

            if existing:
                # Update existing record
                existing.deal_name = deal_name
                existing.metric_id = metric_id
                existing.deal_data_hash = deal_hash
                existing.vector_uuid = vector_uuid
                existing.document_content = document_content
                existing.chunk_count = chunk_count
                existing.hubspot_updated_at = hubspot_updated_at
                existing.last_ingested_at = datetime.now(UTC)
                existing.ingestion_status = status
                existing.error_message = error_message
                existing.extra_metadata = metadata
            else:
                # Create new record
                new_record = HubSpotDealTracking(
                    hubspot_deal_id=hubspot_deal_id,
                    deal_name=deal_name,
                    metric_id=metric_id,
                    deal_data_hash=deal_hash,
                    vector_uuid=vector_uuid,
                    document_content=document_content,
                    chunk_count=chunk_count,
                    hubspot_updated_at=hubspot_updated_at,
                    ingestion_status=status,
                    error_message=error_message,
                    extra_metadata=metadata,
                )
                session.add(new_record)

            session.commit()

    def get_deal_by_hubspot_id(self, deal_id: str) -> dict[str, Any] | None:
        """
        Get deal tracking information by HubSpot deal ID.

        Args:
            deal_id: HubSpot deal ID

        Returns:
            Dictionary with deal tracking info or None if not found
        """
        with get_data_db_session() as session:
            deal = (
                session.query(HubSpotDealTracking)
                .filter_by(hubspot_deal_id=deal_id)
                .first()
            )

            if not deal:
                return None

            return {
                "hubspot_deal_id": deal.hubspot_deal_id,
                "deal_name": deal.deal_name,
                "deal_data_hash": deal.deal_data_hash,
                "vector_uuid": deal.vector_uuid,
                "chunk_count": deal.chunk_count,
                "hubspot_updated_at": deal.hubspot_updated_at.isoformat()
                if deal.hubspot_updated_at
                else None,
                "first_ingested_at": deal.first_ingested_at.isoformat()
                if deal.first_ingested_at
                else None,
                "last_ingested_at": deal.last_ingested_at.isoformat()
                if deal.last_ingested_at
                else None,
                "ingestion_status": deal.ingestion_status,
                "error_message": deal.error_message,
                "metadata": deal.extra_metadata,
            }

    def get_all_synced_deals(self) -> list[dict[str, Any]]:
        """
        Get all synced deals with their tracking info.

        Returns:
            List of deal tracking info dictionaries
        """
        with get_data_db_session() as session:
            deals = (
                session.query(HubSpotDealTracking)
                .order_by(HubSpotDealTracking.last_ingested_at.desc())
                .all()
            )

            return [
                {
                    "hubspot_deal_id": deal.hubspot_deal_id,
                    "deal_name": deal.deal_name,
                    "deal_data_hash": deal.deal_data_hash[:16],  # Shortened for display
                    "vector_uuid": deal.vector_uuid,
                    "last_ingested_at": deal.last_ingested_at.isoformat()
                    if deal.last_ingested_at
                    else None,
                    "ingestion_status": deal.ingestion_status,
                }
                for deal in deals
            ]

    def mark_deal_removed(self, deal_id: str) -> bool:
        """
        Mark a deal as removed (no longer in HubSpot).

        Args:
            deal_id: HubSpot deal ID

        Returns:
            True if deal was found and marked, False otherwise
        """
        with get_data_db_session() as session:
            deal = (
                session.query(HubSpotDealTracking)
                .filter_by(hubspot_deal_id=deal_id)
                .first()
            )

            if not deal:
                return False

            deal.ingestion_status = "removed"
            deal.last_ingested_at = datetime.now(UTC)
            session.commit()
            return True

    def get_deal_by_name(self, deal_name: str) -> dict[str, Any] | None:
        """
        Get deal tracking information by deal name (fuzzy match).

        Args:
            deal_name: Deal name to search for

        Returns:
            Dictionary with deal tracking info or None if not found
        """
        with get_data_db_session() as session:
            # Try exact match first
            deal = (
                session.query(HubSpotDealTracking)
                .filter_by(deal_name=deal_name)
                .first()
            )

            if not deal:
                # Try partial match (deal name contains search term)
                deal = (
                    session.query(HubSpotDealTracking)
                    .filter(HubSpotDealTracking.deal_name.ilike(f"%{deal_name}%"))
                    .first()
                )

            if not deal:
                return None

            return {
                "hubspot_deal_id": deal.hubspot_deal_id,
                "deal_name": deal.deal_name,
                "document_content": deal.document_content,
                "metadata": deal.extra_metadata,
            }

    def get_tech_stack_for_deal(self, deal_id: str) -> list[str]:
        """
        Extract tech stack from a stored deal's document content.

        Args:
            deal_id: HubSpot deal ID

        Returns:
            List of tech stack items, empty if not found
        """
        with get_data_db_session() as session:
            deal = (
                session.query(HubSpotDealTracking)
                .filter_by(hubspot_deal_id=deal_id)
                .first()
            )

            if not deal or not deal.document_content:
                return []

            # Parse tech stack from document content
            # Format: "Deal Tech Requirements: tech1, tech2, tech3"
            # and "Company Tech Stack: tech1, tech2"
            tech_stack = []
            content = deal.document_content

            for line in content.split("\n"):
                if "Deal Tech Requirements:" in line or "Company Tech Stack:" in line:
                    tech_part = line.split(":", 1)[1].strip()
                    if tech_part and tech_part != "Not specified":
                        tech_stack.extend([t.strip() for t in tech_part.split(",")])

            # Deduplicate and return
            return list(set(tech_stack))

    def get_tech_stack_by_client_name(self, client_name: str) -> list[str]:
        """
        Find tech stack for a client by matching deal names.

        Args:
            client_name: Client/company name to search for

        Returns:
            Combined tech stack from matching deals
        """
        with get_data_db_session() as session:
            # Search for deals where deal_name contains the client name
            deals = (
                session.query(HubSpotDealTracking)
                .filter(HubSpotDealTracking.deal_name.ilike(f"%{client_name}%"))
                .all()
            )

            if not deals:
                return []

            # Combine tech stacks from all matching deals
            all_tech = []
            for deal in deals:
                if deal.document_content:
                    content = deal.document_content
                    for line in content.split("\n"):
                        if (
                            "Deal Tech Requirements:" in line
                            or "Company Tech Stack:" in line
                        ):
                            tech_part = line.split(":", 1)[1].strip()
                            if tech_part and tech_part != "Not specified":
                                all_tech.extend(
                                    [t.strip() for t in tech_part.split(",")]
                                )

            return list(set(all_tech))

    def get_tech_stack_by_metric_id(self, metric_project_id: str) -> list[str]:
        """
        Find tech stack for a Metric project by its ID.

        Uses the indexed metric_id column for fast lookup.

        Args:
            metric_project_id: Metric.ai project ID (e.g., "70850")

        Returns:
            List of tech stack items from the linked HubSpot deal
        """
        with get_data_db_session() as session:
            # Query by indexed metric_id column (fast lookup)
            deals = (
                session.query(HubSpotDealTracking)
                .filter(HubSpotDealTracking.metric_id == metric_project_id)
                .all()
            )

            # Fallback: search in document_content if column not populated yet
            if not deals:
                deals = (
                    session.query(HubSpotDealTracking)
                    .filter(
                        HubSpotDealTracking.document_content.ilike(
                            f"%Metric Project ID: {metric_project_id}%"
                        )
                    )
                    .all()
                )

            if not deals:
                return []

            # Extract tech stack from matching deals
            all_tech = []
            for deal in deals:
                if deal.document_content:
                    content = deal.document_content
                    for line in content.split("\n"):
                        if (
                            "Deal Tech Requirements:" in line
                            or "Company Tech Stack:" in line
                        ):
                            tech_part = line.split(":", 1)[1].strip()
                            if tech_part and tech_part != "Not specified":
                                all_tech.extend(
                                    [t.strip() for t in tech_part.split(",")]
                                )

            return list(set(all_tech))

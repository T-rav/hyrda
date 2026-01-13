"""Metric.ai record model for staging/tracking synced data."""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class MetricRecord(Base):
    """Staging table to track what has been synced from Metric.ai to Pinecone."""

    __tablename__ = "metric_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Metric.ai identification
    metric_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Metric.ai record ID (e.g., emp_123)",
    )
    data_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type: employee, project, client, allocation",
    )

    # Pinecone reference
    pinecone_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Pinecone vector ID (metric_{metric_id})",
    )
    pinecone_namespace = Column(
        String(100), nullable=False, default="metric", comment="Pinecone namespace"
    )

    # Content staging
    content_snapshot = Column(
        Text, nullable=False, comment="Text content synced to Pinecone"
    )

    # Timestamps
    created_at = Column(
        DateTime, nullable=False, default=func.now(), comment="First sync timestamp"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Last sync timestamp",
    )
    synced_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        comment="Last Pinecone sync timestamp",
    )

    def __repr__(self) -> str:
        return f"<MetricRecord(id={self.id}, metric_id={self.metric_id}, data_type={self.data_type})>"

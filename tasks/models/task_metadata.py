"""Task metadata model for storing custom task names and descriptions."""

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TaskMetadata(Base):
    """Store custom metadata for scheduled tasks."""

    __tablename__ = "task_metadata"

    job_id = Column(String(191), primary_key=True)
    task_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "task_name": self.task_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

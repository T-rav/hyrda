"""Portal employee data synchronization job."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import TasksSettings
from services.openai_embeddings import OpenAIEmbeddings
from services.pinecone_client import PineconeClient
from services.portal_client import PortalClient

from .base_job import BaseJob

logger = logging.getLogger(__name__)


def clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Remove null values from metadata (Pinecone doesn't accept nulls)."""
    return {k: v for k, v in metadata.items() if v is not None}


class PortalSyncJob(BaseJob):
    """Job to sync employee profile and skills data from Portal Backend V2."""

    JOB_NAME = "Portal Employee Sync"
    JOB_DESCRIPTION = (
        "Sync employee profiles and skills from Portal Backend V2 to Pinecone"
    )
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = []

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the Portal sync job."""
        super().__init__(settings, **kwargs)

        # Initialize clients
        self.portal_client = PortalClient()
        self.embedding_client = OpenAIEmbeddings()
        self.vector_client = PineconeClient()

        # Get data database URL from settings (uses sync driver for database writes)
        self.data_db_url = self.settings.data_database_url

    def _write_portal_records(self, records: list[dict[str, Any]]) -> int:
        """
        Write portal records to the insightmesh_data database.

        Args:
            records: List of dicts with keys: employee_id, data_type, pinecone_id,
                    pinecone_namespace, content_snapshot

        Returns:
            Number of records written
        """
        session = None
        try:
            # Create engine and session
            data_engine = create_engine(self.data_db_url)
            DataSession = sessionmaker(bind=data_engine)
            session = DataSession()

            now = datetime.now(UTC)
            is_sqlite = "sqlite" in self.data_db_url.lower()

            for record in records:
                if is_sqlite:
                    # SQLite: Use INSERT OR REPLACE
                    session.execute(
                        text("""
                        INSERT OR REPLACE INTO portal_records
                        (employee_id, data_type, pinecone_id, pinecone_namespace, content_snapshot,
                         created_at, updated_at, synced_at)
                        VALUES (:employee_id, :data_type, :pinecone_id, :namespace, :content,
                                :now, :now, :now)
                        """),
                        {
                            "employee_id": record["employee_id"],
                            "data_type": record["data_type"],
                            "pinecone_id": record["pinecone_id"],
                            "namespace": record["pinecone_namespace"],
                            "content": record["content_snapshot"],
                            "now": now,
                        },
                    )
                else:
                    # MySQL: Use ON DUPLICATE KEY UPDATE
                    session.execute(
                        text("""
                        INSERT INTO portal_records
                        (employee_id, data_type, pinecone_id, pinecone_namespace, content_snapshot,
                         created_at, updated_at, synced_at)
                        VALUES (:employee_id, :data_type, :pinecone_id, :namespace, :content,
                                :now, :now, :now)
                        ON DUPLICATE KEY UPDATE
                            content_snapshot = VALUES(content_snapshot),
                            updated_at = VALUES(updated_at),
                            synced_at = VALUES(synced_at)
                        """),
                        {
                            "employee_id": record["employee_id"],
                            "data_type": record["data_type"],
                            "pinecone_id": record["pinecone_id"],
                            "namespace": record["pinecone_namespace"],
                            "content": record["content_snapshot"],
                            "now": now,
                        },
                    )
            session.commit()
            return len(records)
        except Exception as e:
            logger.error(f"Error writing to portal_records: {e}")
            if session:
                session.rollback()
            return 0
        finally:
            if session:
                session.close()

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the Portal employee data sync."""
        stats = {
            "employees_synced": 0,
            "skills_synced": 0,
            "errors": [],
        }

        try:
            # Initialize Pinecone
            await self.vector_client.initialize()

            # Sync employee profiles and skills
            (
                stats["employees_synced"],
                stats["skills_synced"],
            ) = await self._sync_employees()

            # Close connections
            await self.vector_client.close()

            logger.info(f"✅ Portal sync completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Portal sync failed: {e}")
            stats["errors"].append(str(e))
            raise

    async def _sync_employees(self) -> tuple[int, int]:
        """
        Sync employee data from Portal to Pinecone.

        Returns:
            Tuple of (employees_synced, total_skills_synced)
        """
        logger.info("Syncing employees from Portal...")

        employees = self.portal_client.get_employees()
        if not employees:
            return 0, 0

        texts, metadata_list = [], []
        total_skills = 0

        for employee in employees:
            # Extract profile and skills
            profile = employee.get("profile", {})
            skills = profile.get("skills", [])
            total_skills += len(skills)

            # Build skills text for embedding
            technical_skills = [
                s["skill"] for s in skills if s.get("category") == "Technical"
            ]
            domain_skills = [
                s["skill"] for s in skills if s.get("category") == "Domain"
            ]
            industry_skills = [
                s["skill"] for s in skills if s.get("category") == "Industry"
            ]

            # Build interest-based skills
            interested_skills = [
                s["skill"] for s in skills if s.get("interest") is True
            ]
            expert_skills = [s["skill"] for s in skills if s.get("level", 0) >= 3]

            # Build current and past allocations text
            current_allocations = employee.get("current_billable_allocations", [])
            past_allocations = employee.get("past_billable_allocations", [])

            current_projects = [
                alloc.get("project_name", "") for alloc in current_allocations
            ]
            past_projects = [
                alloc.get("project_name", "") for alloc in past_allocations
            ]

            # Create searchable text with rich employee profile
            text = f"Employee: {employee['name']}\n"
            text += f"Email: {employee.get('email', 'N/A')}\n"
            text += f"Department: {employee.get('department', 'N/A')}\n"
            text += f"Role: {employee.get('role', 'N/A')}\n"
            text += f"Practice: {employee.get('practice', 'N/A')}\n"
            text += f"On Bench: {'Yes' if employee.get('on_bench') else 'No'}\n"
            text += f"Started: {employee.get('started_working', 'N/A')}\n"

            if technical_skills:
                text += f"Technical Skills: {', '.join(technical_skills)}\n"
            if domain_skills:
                text += f"Domain Skills: {', '.join(domain_skills)}\n"
            if industry_skills:
                text += f"Industry Experience: {', '.join(industry_skills)}\n"
            if expert_skills:
                text += f"Expert Level Skills: {', '.join(expert_skills)}\n"
            if interested_skills:
                text += f"Interested In: {', '.join(interested_skills)}\n"

            if profile.get("client_bio"):
                text += f"Client Bio: {profile['client_bio']}\n"
            if profile.get("tech_experience"):
                text += f"Tech Experience: {profile['tech_experience']}\n"

            if current_projects:
                text += f"Current Projects: {', '.join(current_projects)}\n"
            if past_projects:
                text += f"Past Projects: {', '.join(past_projects)}\n"

            # Create metadata with source="portal"
            metadata = {
                "source": "portal",
                "record_type": "employee",
                "data_type": "employee_profile",
                "employee_id": employee["metric_id"],
                "name": employee["name"],
                "email": employee.get("email", ""),
                "department": employee.get("department", ""),
                "role": employee.get("role", ""),
                "practice": employee.get("practice", ""),
                "on_bench": employee.get("on_bench", False),
                "skills_count": len(skills),
                "technical_skills_count": len(technical_skills),
                "domain_skills_count": len(domain_skills),
                "industry_skills_count": len(industry_skills),
                "current_projects_count": len(current_projects),
                "past_projects_count": len(past_projects),
                "synced_at": datetime.now(UTC).isoformat(),
            }

            texts.append(text)
            metadata_list.append(clean_metadata(metadata))

        # Generate embeddings and upsert to Pinecone
        embeddings = self.embedding_client.embed_batch(texts)
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="portal"
        )

        # Write to portal_records table
        db_records = [
            {
                "employee_id": emp["metric_id"],
                "data_type": "employee_profile",
                "pinecone_id": f"portal_employee_{emp['metric_id']}",
                "pinecone_namespace": "portal",
                "content_snapshot": texts[i],
            }
            for i, emp in enumerate(employees)
        ]
        db_written = self._write_portal_records(db_records)

        logger.info(
            f"✅ Synced {len(employees)} employees ({total_skills} total skills) to Pinecone and {db_written} to database"
        )
        return len(employees), total_skills

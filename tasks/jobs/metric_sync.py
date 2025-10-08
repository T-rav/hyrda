"""Metric.ai data synchronization job - STANDALONE (no bot dependencies)."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import TasksSettings
from services.metric_client import MetricClient
from services.openai_embeddings import OpenAIEmbeddings
from services.qdrant_client import QdrantClient

from .base_job import BaseJob

logger = logging.getLogger(__name__)


def clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Remove null values from metadata."""
    return {k: v for k, v in metadata.items() if v is not None}


class MetricSyncJob(BaseJob):
    """Job to sync employee, project, client, and allocation data from Metric.ai."""

    JOB_NAME = "Metric.ai Data Sync"
    JOB_DESCRIPTION = "Sync employees, projects, and clients from Metric.ai to Qdrant"
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = [
        "sync_employees",
        "sync_projects",
        "sync_clients",
    ]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the Metric.ai sync job."""
        super().__init__(settings, **kwargs)

        # Initialize clients
        self.metric_client = MetricClient()
        self.embedding_client = OpenAIEmbeddings()
        self.vector_client = QdrantClient()

        # Store which data types to sync (default: all)
        self.sync_employees = self.params.get("sync_employees", True)
        self.sync_projects = self.params.get("sync_projects", True)
        self.sync_clients = self.params.get("sync_clients", True)

        # Allocations start year for building employee project history
        self.allocations_start_year = 2020

        # Get data database URL from settings (uses sync driver for database writes)
        self.data_db_url = self.settings.data_database_url

    def _get_data_session(self):
        """Create database session for insightmesh_data database."""
        data_engine = create_engine(self.data_db_url)
        DataSession = sessionmaker(bind=data_engine)
        return DataSession()

    def _write_metric_records(self, records: list[dict[str, Any]]) -> int:
        """
        Write metric records to the insightmesh_data database.

        Args:
            records: List of dicts with keys: metric_id, data_type, vector_id,
                    vector_namespace, content_snapshot

        Returns:
            Number of records written
        """
        session = None
        try:
            # Create engine and session without context manager
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
                        INSERT OR REPLACE INTO metric_records
                        (metric_id, data_type, vector_id, vector_namespace, content_snapshot,
                         created_at, updated_at, synced_at)
                        VALUES (:metric_id, :data_type, :vector_id, :namespace, :content,
                                :now, :now, :now)
                        """),
                        {
                            "metric_id": record["metric_id"],
                            "data_type": record["data_type"],
                            "vector_id": record["vector_id"],
                            "namespace": record["vector_namespace"],
                            "content": record["content_snapshot"],
                            "now": now,
                        },
                    )
                else:
                    # MySQL: Use ON DUPLICATE KEY UPDATE
                    session.execute(
                        text("""
                        INSERT INTO metric_records
                        (metric_id, data_type, vector_id, vector_namespace, content_snapshot,
                         created_at, updated_at, synced_at)
                        VALUES (:metric_id, :data_type, :vector_id, :namespace, :content,
                                :now, :now, :now)
                        ON DUPLICATE KEY UPDATE
                            content_snapshot = VALUES(content_snapshot),
                            updated_at = VALUES(updated_at),
                            synced_at = VALUES(synced_at)
                        """),
                        {
                            "metric_id": record["metric_id"],
                            "data_type": record["data_type"],
                            "vector_id": record["vector_id"],
                            "namespace": record["vector_namespace"],
                            "content": record["content_snapshot"],
                            "now": now,
                        },
                    )
            session.commit()
            return len(records)
        except Exception as e:
            logger.error(f"Error writing to metric_records: {e}")
            if session:
                session.rollback()
            return 0
        finally:
            if session:
                session.close()

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the Metric.ai data sync."""
        stats = {
            "employees_synced": 0,
            "projects_synced": 0,
            "clients_synced": 0,
            "allocations_synced": 0,
            "errors": [],
        }

        try:
            # Initialize Qdrant
            await self.vector_client.initialize()

            # Sync each data type
            if self.sync_employees:
                stats["employees_synced"] = await self._sync_employees()

            if self.sync_clients:
                stats["clients_synced"] = await self._sync_clients()

            if self.sync_projects:
                stats["projects_synced"] = await self._sync_projects()

            # Close connections
            await self.vector_client.close()

            logger.info(f"✅ Metric.ai sync completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Metric.ai sync failed: {e}")
            stats["errors"].append(str(e))
            raise

    async def _sync_employees(self) -> int:
        """Sync employee data from Metric.ai to Qdrant."""
        logger.info("Syncing employees from Metric.ai...")

        employees = self.metric_client.get_employees()
        if not employees:
            return 0

        # Get all allocations to build project history
        logger.info("Fetching allocations for project history...")
        current_year = datetime.now(UTC).year
        all_allocations = []
        for year in range(self.allocations_start_year, current_year + 1):
            start_date = f"{year}-01-01"
            end_date = f"{year + 1}-01-01"
            try:
                allocations = self.metric_client.get_allocations(start_date, end_date)
                all_allocations.extend(allocations)
            except Exception as e:
                logger.warning(f"Failed to fetch allocations for {year}: {e}")

        # Build employee -> projects mapping
        employee_projects = {}
        for alloc in all_allocations:
            if not alloc or not alloc.get("id"):
                continue

            employee = alloc.get("employee")
            if not employee or not isinstance(employee, dict) or not employee.get("id"):
                continue

            project = alloc.get("project")
            if not project or not isinstance(project, dict) or not project.get("name"):
                continue

            emp_id = employee["id"]
            project_name = project["name"]
            if emp_id not in employee_projects:
                employee_projects[emp_id] = set()
            employee_projects[emp_id].add(project_name)

        texts, metadata_list = [], []

        for employee in employees:
            # Extract bench status
            on_bench = any(
                g["groupType"] == "GROUP_TYPE_17" and g["name"] == "True"
                for g in employee.get("groups", [])
            )

            # Get project history for this employee
            projects = employee_projects.get(employee["id"], set())
            project_history = (
                ", ".join(sorted(projects)) if projects else "No project history"
            )

            # Create searchable text with project history
            text = (
                f"Employee: {employee['name']}\n"
                f"Email: {employee.get('email', 'N/A')}\n"
                f"Status: {'On Bench' if on_bench else 'Allocated'}\n"
                f"Started: {employee.get('startedWorking', 'N/A')}\n"
                f"Ended: {employee.get('endedWorking', 'Active')}\n"
                f"Project History: {project_history}"
            )

            # Create metadata with source="metric"
            metadata = {
                "source": "metric",
                "record_type": "employee",
                "data_type": "employee",
                "employee_id": employee["id"],
                "name": employee["name"],
                "email": employee.get("email", ""),
                "on_bench": on_bench,
                "started_working": employee.get("startedWorking", ""),
                "ended_working": employee.get("endedWorking", ""),
                "project_count": len(projects),
                "synced_at": datetime.now(UTC).isoformat(),
            }

            texts.append(text)
            metadata_list.append(clean_metadata(metadata))

        # Generate embeddings and upsert to Qdrant
        embeddings = self.embedding_client.embed_batch(texts)
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="metric"
        )

        # Write to metric_records table
        db_records = [
            {
                "metric_id": emp["id"],
                "data_type": "employee",
                "vector_id": f"metric_employee_{emp['id']}",
                "vector_namespace": "metric",
                "content_snapshot": texts[i],
            }
            for i, emp in enumerate(employees)
        ]
        db_written = self._write_metric_records(db_records)

        logger.info(
            f"✅ Synced {len(employees)} employees to Qdrant and {db_written} to database"
        )
        return len(employees)

    async def _sync_projects(self) -> int:
        """Sync project data from Metric.ai to Qdrant."""
        logger.info("Syncing projects from Metric.ai...")

        projects = self.metric_client.get_projects()
        texts, metadata_list = [], []

        for project in projects:
            # Skip non-billable projects
            if project.get("projectType") != "BILLABLE":
                continue

            # Skip projects without groups
            if not project.get("groups"):
                continue

            # Extract client
            client = next(
                (g["name"] for g in project["groups"] if g["groupType"] == "CLIENT"),
                "Unknown Client",
            )

            # Skip if no client
            if client == "Unknown Client":
                continue

            # Extract delivery owner, billing frequency, and practice
            delivery_owner = next(
                (
                    g["name"]
                    for g in project["groups"]
                    if g["groupType"] == "GROUP_TYPE_12"
                ),
                "Unknown",
            )
            billing_frequency = next(
                (
                    g["name"]
                    for g in project["groups"]
                    if g["groupType"] == "GROUP_TYPE_7"
                ),
                "Unknown",
            )
            practice = next(
                (
                    g["name"]
                    for g in project["groups"]
                    if g["groupType"] == "GROUP_TYPE_21"
                ),
                "Unknown",
            )

            # Create searchable text with practice
            text = (
                f"Project: {project['name']}\n"
                f"Client: {client}\n"
                f"Practice: {practice}\n"
                f"Type: {project.get('projectType', 'Unknown')}\n"
                f"Status: {project.get('projectStatus', 'Unknown')}\n"
                f"Start Date: {project.get('startDate', 'N/A')}\n"
                f"End Date: {project.get('endDate', 'N/A')}\n"
                f"Delivery Owner: {delivery_owner}\n"
                f"Billing Frequency: {billing_frequency}"
            )

            # Create metadata with source="metric"
            metadata = {
                "source": "metric",
                "record_type": "project",
                "data_type": "project",
                "project_id": project["id"],
                "name": project["name"],
                "client": client,
                "practice": practice,
                "project_type": project.get("projectType", ""),
                "project_status": project.get("projectStatus", ""),
                "start_date": project.get("startDate", ""),
                "end_date": project.get("endDate", ""),
                "delivery_owner": delivery_owner,
                "billing_frequency": billing_frequency,
                "synced_at": datetime.now(UTC).isoformat(),
            }

            texts.append(text)
            metadata_list.append(clean_metadata(metadata))

        if texts:
            # Upsert to Qdrant
            embeddings = self.embedding_client.embed_batch(texts)
            await self.vector_client.upsert_with_namespace(
                texts, embeddings, metadata_list, namespace="metric"
            )

            # Write to metric_records table
            db_records = [
                {
                    "metric_id": metadata_list[i]["project_id"],
                    "data_type": "project",
                    "vector_id": f"metric_project_{metadata_list[i]['project_id']}",
                    "vector_namespace": "metric",
                    "content_snapshot": texts[i],
                }
                for i in range(len(texts))
            ]
            db_written = self._write_metric_records(db_records)

            logger.info(
                f"✅ Synced {len(texts)} projects to Qdrant and {db_written} to database (filtered from {len(projects)} total)"
            )
        return len(texts)

    async def _sync_clients(self) -> int:
        """Sync client data from Metric.ai to Qdrant."""
        logger.info("Syncing clients from Metric.ai...")

        clients = self.metric_client.get_clients()
        if not clients:
            return 0

        texts, metadata_list = [], []

        for client in clients:
            # Create searchable text
            text = f"Client: {client['name']}\nClient ID: {client['id']}"

            # Create metadata with source="metric"
            metadata = {
                "source": "metric",
                "record_type": "client",
                "data_type": "client",
                "client_id": client["id"],
                "name": client["name"],
                "synced_at": datetime.now(UTC).isoformat(),
            }

            texts.append(text)
            metadata_list.append(clean_metadata(metadata))

        # Generate embeddings and upsert to Qdrant
        embeddings = self.embedding_client.embed_batch(texts)
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="metric"
        )

        # Write to metric_records table
        db_records = [
            {
                "metric_id": clients[i]["id"],
                "data_type": "client",
                "vector_id": f"metric_client_{clients[i]['id']}",
                "vector_namespace": "metric",
                "content_snapshot": texts[i],
            }
            for i in range(len(clients))
        ]
        db_written = self._write_metric_records(db_records)

        logger.info(
            f"✅ Synced {len(clients)} clients to Qdrant and {db_written} to database"
        )
        return len(clients)

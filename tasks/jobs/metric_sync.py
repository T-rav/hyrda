"""Metric.ai data synchronization job - STANDALONE (no bot dependencies)."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import TasksSettings
from services.metric_client import MetricClient
from services.openai_embeddings import OpenAIEmbeddings
from services.pinecone_client import PineconeClient

from .base_job import BaseJob

logger = logging.getLogger(__name__)


def clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Remove null values from metadata (Pinecone doesn't accept nulls)."""
    return {k: v for k, v in metadata.items() if v is not None}


class MetricSyncJob(BaseJob):
    """Job to sync employee, project, client, and allocation data from Metric.ai."""

    JOB_NAME = "Metric.ai Data Sync"
    JOB_DESCRIPTION = (
        "Sync employees, projects, clients, and allocations from Metric.ai to Pinecone"
    )
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = [
        "sync_employees",
        "sync_projects",
        "sync_clients",
        "sync_allocations",
        "allocations_start_year",
    ]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the Metric.ai sync job."""
        super().__init__(settings, **kwargs)

        # Initialize clients
        self.metric_client = MetricClient()
        self.embedding_client = OpenAIEmbeddings()
        self.vector_client = PineconeClient()

        # Store which data types to sync (default: all)
        self.sync_employees = self.params.get("sync_employees", True)
        self.sync_projects = self.params.get("sync_projects", True)
        self.sync_clients = self.params.get("sync_clients", True)
        self.sync_allocations = self.params.get("sync_allocations", True)
        self.allocations_start_year = self.params.get("allocations_start_year", 2020)

        # Get data database URL (insightmesh_data)
        self.data_db_url = self.settings.database_url.replace(
            "insightmesh_task", "insightmesh_data"
        )

    def _get_data_session(self):
        """Create database session for insightmesh_data database."""
        data_engine = create_engine(self.data_db_url)
        DataSession = sessionmaker(bind=data_engine)
        return DataSession()

    def _write_metric_records(self, records: list[dict[str, Any]]) -> int:
        """
        Write metric records to the insightmesh_data database.

        Args:
            records: List of dicts with keys: metric_id, data_type, pinecone_id,
                    pinecone_namespace, content_snapshot

        Returns:
            Number of records written
        """
        try:
            with self._get_data_session() as session:
                now = datetime.now(UTC)
                for record in records:
                    # Use raw SQL to insert or update
                    session.execute(
                        text("""
                        INSERT INTO metric_records
                        (metric_id, data_type, pinecone_id, pinecone_namespace, content_snapshot,
                         created_at, updated_at, synced_at)
                        VALUES (:metric_id, :data_type, :pinecone_id, :namespace, :content,
                                :now, :now, :now)
                        ON DUPLICATE KEY UPDATE
                            content_snapshot = :content,
                            updated_at = :now,
                            synced_at = :now
                        """),
                        {
                            "metric_id": record["metric_id"],
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
            logger.error(f"Error writing to metric_records: {e}")
            return 0

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
            # Initialize Pinecone
            await self.vector_client.initialize()

            # Sync each data type
            if self.sync_employees:
                stats["employees_synced"] = await self._sync_employees()

            if self.sync_clients:
                stats["clients_synced"] = await self._sync_clients()

            if self.sync_projects:
                stats["projects_synced"] = await self._sync_projects()

            if self.sync_allocations:
                stats["allocations_synced"] = await self._sync_allocations()

            # Close connections
            await self.vector_client.close()

            logger.info(f"✅ Metric.ai sync completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Metric.ai sync failed: {e}")
            stats["errors"].append(str(e))
            raise

    async def _sync_employees(self) -> int:
        """Sync employee data from Metric.ai to Pinecone."""
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

        # Write to database FIRST, then upsert to Pinecone
        db_records = [
            {
                "metric_id": emp["id"],
                "data_type": "employee",
                "pinecone_id": f"metric_{emp['id']}",
                "pinecone_namespace": "metric",
                "content_snapshot": text,
            }
            for emp, text in zip(employees, texts, strict=False)
        ]

        # Generate embeddings and upsert to Pinecone
        embeddings = self.embedding_client.embed_batch(texts)
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="metric"
        )

        # Write to database with current timestamp as synced_at
        records_written = self._write_metric_records(db_records)
        logger.info(
            f"✅ Synced {len(employees)} employees to Pinecone and database ({records_written} records)"
        )
        return len(employees)

    async def _sync_projects(self) -> int:
        """Sync project data from Metric.ai to Pinecone."""
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
            db_records = [
                {
                    "metric_id": projects[i]["id"],
                    "data_type": "project",
                    "pinecone_id": f"metric_{projects[i]['id']}",
                    "pinecone_namespace": "metric",
                    "content_snapshot": text,
                }
                for i, text in enumerate(texts)
            ]

            # Upsert to Pinecone
            embeddings = self.embedding_client.embed_batch(texts)
            await self.vector_client.upsert_with_namespace(
                texts, embeddings, metadata_list, namespace="metric"
            )

            # Write to database with synced_at timestamp
            records_written = self._write_metric_records(db_records)
            logger.info(
                f"✅ Synced {len(texts)} projects to Pinecone and database ({records_written} records, filtered from {len(projects)} total)"
            )
        return len(texts)

    async def _sync_clients(self) -> int:
        """Sync client data from Metric.ai to Pinecone."""
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

        db_records = [
            {
                "metric_id": cli["id"],
                "data_type": "client",
                "pinecone_id": f"metric_{cli['id']}",
                "pinecone_namespace": "metric",
                "content_snapshot": text,
            }
            for cli, text in zip(clients, texts, strict=False)
        ]

        # Generate embeddings and upsert to Pinecone
        embeddings = self.embedding_client.embed_batch(texts)
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="metric"
        )

        # Write to database with synced_at timestamp
        records_written = self._write_metric_records(db_records)
        logger.info(
            f"✅ Synced {len(clients)} clients to Pinecone and database ({records_written} records)"
        )
        return len(clients)

    async def _sync_allocations(self) -> int:
        """Sync allocation data from Metric.ai to Pinecone."""
        try:
            logger.info("Syncing allocations from Metric.ai...")

            current_year = datetime.now(UTC).year
            all_allocations = []

            # Query year by year from start year to current
            for year in range(self.allocations_start_year, current_year + 1):
                start_date = f"{year}-01-01"
                end_date = f"{year + 1}-01-01"

                try:
                    allocations = self.metric_client.get_allocations(
                        start_date, end_date
                    )
                    all_allocations.extend(allocations)
                    logger.info(f"Fetched {len(allocations)} allocations for {year}")
                except Exception as e:
                    logger.warning(f"Failed to fetch allocations for {year}: {e}")

            logger.info(f"Total allocations fetched: {len(all_allocations)}")

            # Remove duplicates by allocation ID and filter None
            unique_dict = {}
            for alloc in all_allocations:
                if alloc and alloc.get("id"):
                    unique_dict[alloc["id"]] = alloc
            unique_allocations = unique_dict.values()

            logger.info(f"Unique allocations after filtering: {len(unique_dict)}")

            texts, metadata_list, allocation_ids = [], [], []

            for allocation in unique_allocations:
                try:
                    # Skip allocations without valid employee or project
                    if not allocation or not allocation.get("id"):
                        continue

                    employee = allocation.get("employee")
                    if (
                        not employee
                        or not isinstance(employee, dict)
                        or not employee.get("id")
                    ):
                        continue

                    project = allocation.get("project")
                    if (
                        not project
                        or not isinstance(project, dict)
                        or not project.get("id")
                    ):
                        continue

                    employee_name = employee.get("name", "Unknown")
                    project_name = project.get("name", "Unknown")

                    # Create searchable text
                    text = (
                        f"Allocation: {employee_name} on {project_name}\n"
                        f"Start Date: {allocation.get('startDate', 'N/A')}\n"
                        f"End Date: {allocation.get('endDate', 'N/A')}"
                    )

                    # Create metadata with source="metric"
                    metadata = {
                        "source": "metric",
                        "record_type": "allocation",
                        "data_type": "allocation",
                        "allocation_id": allocation["id"],
                        "employee_id": employee["id"],
                        "employee_name": employee_name,
                        "project_id": project["id"],
                        "project_name": project_name,
                        "start_date": allocation.get("startDate", ""),
                        "end_date": allocation.get("endDate", ""),
                        "synced_at": datetime.now(UTC).isoformat(),
                    }

                    texts.append(text)
                    metadata_list.append(clean_metadata(metadata))
                    allocation_ids.append(allocation["id"])
                except Exception as e:
                    logger.warning(
                        f"Skipping allocation due to error: {e}, allocation: {allocation}"
                    )

            if texts:
                db_records = [
                    {
                        "metric_id": alloc_id,
                        "data_type": "allocation",
                        "pinecone_id": f"metric_{alloc_id}",
                        "pinecone_namespace": "metric",
                        "content_snapshot": text,
                    }
                    for alloc_id, text in zip(allocation_ids, texts, strict=False)
                ]

                # Upsert to Pinecone
                embeddings = self.embedding_client.embed_batch(texts)
                await self.vector_client.upsert_with_namespace(
                    texts, embeddings, metadata_list, namespace="metric"
                )

                # Write to database with synced_at timestamp
                records_written = self._write_metric_records(db_records)
                logger.info(
                    f"✅ Synced {len(texts)} allocations to Pinecone and database ({records_written} records, unique from {len(all_allocations)} total)"
                )
                return len(texts)
            else:
                logger.warning("No valid allocations to sync")
                return 0
        except Exception as e:
            logger.error(f"Error in _sync_allocations: {e}", exc_info=True)
            raise

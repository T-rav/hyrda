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
        session = None
        try:
            # Create engine and session without context manager
            data_engine = create_engine(self.data_db_url)
            DataSession = sessionmaker(bind=data_engine)
            session = DataSession()

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

        # Generate embeddings and upsert to Pinecone
        embeddings = self.embedding_client.embed_batch(texts)
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="metric"
        )

        # TODO: Database writes disabled - requires 'cryptography' package and metric_records table setup
        logger.info(
            f"✅ Synced {len(employees)} employees to Pinecone (database writes disabled)"
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
            # Upsert to Pinecone
            embeddings = self.embedding_client.embed_batch(texts)
            await self.vector_client.upsert_with_namespace(
                texts, embeddings, metadata_list, namespace="metric"
            )

            # TODO: Database writes disabled - requires 'cryptography' package and metric_records table setup
            logger.info(
                f"✅ Synced {len(texts)} projects to Pinecone (database writes disabled, filtered from {len(projects)} total)"
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

        # Generate embeddings and upsert to Pinecone
        embeddings = self.embedding_client.embed_batch(texts)
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="metric"
        )

        # TODO: Database writes disabled - requires 'cryptography' package and metric_records table setup
        logger.info(
            f"✅ Synced {len(clients)} clients to Pinecone (database writes disabled)"
        )
        return len(clients)

    async def _sync_allocations(self) -> int:
        """Sync allocation data from Metric.ai to Pinecone."""
        try:
            logger.info("Syncing allocations from Metric.ai...")

            # Build project lookup cache first
            logger.info("Building project lookup cache for allocation enrichment...")
            all_projects = self.metric_client.get_projects()
            project_cache = {p["id"]: p for p in all_projects}
            logger.info(f"Cached {len(project_cache)} projects for enrichment")

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
                    employee_email = employee.get("email", "")
                    project_id = project.get("id")
                    project_name = project.get("name", "Unknown")

                    # Extract project details from cache for richer context
                    project_client = "Unknown Client"
                    project_practice = "Unknown Practice"
                    delivery_owner = "Unknown"
                    project_type = "Unknown"

                    # Look up full project data from cache
                    full_project = project_cache.get(project_id)
                    if full_project and full_project.get("groups"):
                        # Extract client
                        project_client = next(
                            (
                                g["name"]
                                for g in full_project["groups"]
                                if g.get("groupType") == "CLIENT"
                            ),
                            "Unknown Client",
                        )
                        # Extract practice
                        project_practice = next(
                            (
                                g["name"]
                                for g in full_project["groups"]
                                if g.get("groupType") == "GROUP_TYPE_21"
                            ),
                            "Unknown Practice",
                        )
                        # Extract delivery owner
                        delivery_owner = next(
                            (
                                g["name"]
                                for g in full_project["groups"]
                                if g.get("groupType") == "GROUP_TYPE_12"
                            ),
                            "Unknown",
                        )
                        project_type = full_project.get("projectType", "Unknown")

                    # Create enriched searchable text with context and common query keywords
                    text = (
                        f"Team Member Allocation: {employee_name} ({employee_email})\n"
                        f"Role: Engineer/Developer working on {project_name}\n"
                        f"Client: {project_client}\n"
                        f"Practice Area: {project_practice}\n"
                        f"Delivery Owner: {delivery_owner}\n"
                        f"Project Type: {project_type}\n"
                        f"Allocation Period: {allocation.get('startDate', 'N/A')} to {allocation.get('endDate', 'N/A')}\n\n"
                        f"Summary: {employee_name} is an engineer who worked on the {project_name} project for {project_client}. "
                        f"This team member was allocated to {project_name} under delivery owner {delivery_owner} "
                        f"in the {project_practice} practice area. "
                        f"As a developer on this project, {employee_name} contributed engineering work from "
                        f"{allocation.get('startDate', 'N/A')} to {allocation.get('endDate', 'N/A')}."
                    )

                    # Create metadata with source="metric" and enriched fields
                    metadata = {
                        "source": "metric",
                        "record_type": "allocation",
                        "data_type": "allocation",
                        "allocation_id": allocation["id"],
                        "employee_id": employee["id"],
                        "employee_name": employee_name,
                        "employee_email": employee_email,
                        "project_id": project["id"],
                        "project_name": project_name,
                        "client": project_client,
                        "practice": project_practice,
                        "delivery_owner": delivery_owner,
                        "project_type": project_type,
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
                # Upsert to Pinecone
                embeddings = self.embedding_client.embed_batch(texts)
                await self.vector_client.upsert_with_namespace(
                    texts, embeddings, metadata_list, namespace="metric"
                )

                # TODO: Database writes disabled - requires 'cryptography' package and metric_records table setup
                logger.info(
                    f"✅ Synced {len(texts)} allocations to Pinecone (database writes disabled, unique from {len(all_allocations)} total)"
                )
                return len(texts)
            else:
                logger.warning("No valid allocations to sync")
                return 0
        except Exception as e:
            logger.error(f"Error in _sync_allocations: {e}", exc_info=True)
            raise

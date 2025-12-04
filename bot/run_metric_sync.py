"""Manual script to run Metric.ai sync job from bot context."""

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Load environment variables from root .env
from dotenv import load_dotenv

root_env = Path(__file__).parent.parent / ".env"
load_dotenv(root_env)
print(f"📄 Loaded environment from: {root_env}\n")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Add tasks directory to path for MetricClient
tasks_path = Path(__file__).parent.parent / "tasks"
sys.path.append(str(tasks_path))

# Now import bot modules (including MetricClient from tasks/)
from services.metric_client import MetricClient  # type: ignore[reportMissingImports]

from config.settings import EmbeddingSettings, VectorSettings
from services.embedding import create_embedding_provider
from services.vector_service import create_vector_store


class MetricSyncRunner:
    """Standalone runner for Metric.ai sync."""

    def __init__(self):
        """Initialize the runner."""
        self.metric_client = MetricClient()
        self.vector_settings = VectorSettings()
        self.embedding_settings = EmbeddingSettings()
        self.stats = {
            "employees_synced": 0,
            "projects_synced": 0,
            "clients_synced": 0,
            "allocations_synced": 0,
            "errors": [],
        }

    async def run(self):
        """Run the sync."""
        print("🚀 Starting Metric.ai sync job...")
        print(f"📊 Vector Provider: {self.vector_settings.provider}")
        print(f"🔤 Embedding Provider: {self.embedding_settings.provider}\n")

        try:
            # Initialize services
            vector_store = create_vector_store(self.vector_settings)
            await vector_store.initialize()

            embedding_provider = create_embedding_provider(self.embedding_settings)

            # Sync each data type
            print("Syncing employees...")
            self.stats["employees_synced"] = await self._sync_employees(
                vector_store, embedding_provider
            )

            print("Syncing clients...")
            self.stats["clients_synced"] = await self._sync_clients(
                vector_store, embedding_provider
            )

            print("Syncing projects...")
            self.stats["projects_synced"] = await self._sync_projects(
                vector_store, embedding_provider
            )

            print("Syncing allocations...")
            self.stats["allocations_synced"] = await self._sync_allocations(
                vector_store, embedding_provider
            )

            await vector_store.close()

            print("\n✅ Metric.ai sync completed successfully!")
            return self.stats

        except Exception as e:
            print(f"\n❌ Metric.ai sync failed: {e}")
            self.stats["errors"].append(str(e))
            raise

    async def _sync_employees(self, vector_store, embedding_provider) -> int:
        """Sync employees - simplified inline implementation."""
        employees = self.metric_client.get_employees()
        if not employees:
            return 0

        texts, metadata_list = [], []
        for emp in employees:
            role = next(
                (
                    g["name"]
                    for g in emp.get("groups", [])
                    if g["groupType"] == "GROUP_TYPE_11"
                ),
                "Unknown",
            )
            dept = next(
                (
                    g["name"]
                    for g in emp.get("groups", [])
                    if g["groupType"] == "DEPARTMENT"
                ),
                "Unknown",
            )
            practice = next(
                (
                    g["name"]
                    for g in emp.get("groups", [])
                    if g["groupType"] == "GROUP_TYPE_23"
                ),
                "Unknown",
            )
            on_bench = any(
                g["groupType"] == "GROUP_TYPE_17" and g["name"] == "True"
                for g in emp.get("groups", [])
            )

            text = (
                f"Employee: {emp['name']}\n"
                f"Email: {emp.get('email', 'N/A')}\n"
                f"Role: {role}\n"
                f"Department: {dept}\n"
                f"Practice: {practice}\n"
                f"Status: {'On Bench' if on_bench else 'Allocated'}"
            )

            metadata = {
                "source": "metric",
                "data_type": "employee",
                "employee_id": emp["id"],
                "name": emp["name"],
                "role": role,
                "department": dept,
                "practice": practice,
                "on_bench": on_bench,
                "synced_at": datetime.now(UTC).isoformat(),
            }

            texts.append(text)
            metadata_list.append(metadata)

        embeddings = embedding_provider.embed_batch(texts)
        await self._add_to_vector_store(vector_store, texts, embeddings, metadata_list)
        return len(employees)

    async def _sync_clients(self, vector_store, embedding_provider) -> int:
        """Sync clients."""
        clients = self.metric_client.get_clients()
        if not clients:
            return 0

        texts, metadata_list = [], []
        for client in clients:
            text = f"Client: {client['name']}\nClient ID: {client['id']}"
            metadata = {
                "source": "metric",
                "data_type": "client",
                "client_id": client["id"],
                "name": client["name"],
                "synced_at": datetime.now(UTC).isoformat(),
            }
            texts.append(text)
            metadata_list.append(metadata)

        embeddings = embedding_provider.embed_batch(texts)
        await self._add_to_vector_store(vector_store, texts, embeddings, metadata_list)
        return len(clients)

    async def _sync_projects(self, vector_store, embedding_provider) -> int:
        """Sync projects (billable only)."""
        projects = self.metric_client.get_projects()
        texts, metadata_list = [], []

        for proj in projects:
            if proj.get("projectType") != "BILLABLE" or not proj.get("groups"):
                continue

            client = next(
                (g["name"] for g in proj["groups"] if g["groupType"] == "CLIENT"),
                "Unknown",
            )
            if client == "Unknown":
                continue

            delivery_owner = next(
                (
                    g["name"]
                    for g in proj["groups"]
                    if g["groupType"] == "GROUP_TYPE_12"
                ),
                "Unknown",
            )

            text = (
                f"Project: {proj['name']}\n"
                f"Client: {client}\n"
                f"Status: {proj.get('projectStatus', 'Unknown')}\n"
                f"Delivery Owner: {delivery_owner}"
            )

            metadata = {
                "source": "metric",
                "data_type": "project",
                "project_id": proj["id"],
                "name": proj["name"],
                "client": client,
                "project_status": proj.get("projectStatus", ""),
                "delivery_owner": delivery_owner,
                "synced_at": datetime.now(UTC).isoformat(),
            }

            texts.append(text)
            metadata_list.append(metadata)

        if texts:
            embeddings = embedding_provider.embed_batch(texts)
            await self._add_to_vector_store(
                vector_store, texts, embeddings, metadata_list
            )

        return len(texts)

    async def _sync_allocations(self, vector_store, embedding_provider) -> int:
        """Sync allocations."""
        current_year = datetime.now(UTC).year
        all_allocations = []

        # Query year by year from 2020
        for year in range(2020, current_year + 1):
            try:
                allocs = self.metric_client.get_allocations(
                    f"{year}-01-01", f"{year + 1}-01-01"
                )
                all_allocations.extend(allocs)
            except Exception as e:
                print(f"Warning: Failed to fetch {year} allocations: {e}")

        # Remove duplicates
        unique_allocs = {a["id"]: a for a in all_allocations}.values()

        texts, metadata_list = [], []
        for alloc in unique_allocs:
            if not alloc.get("employee", {}).get("id") or not alloc.get(
                "project", {}
            ).get("id"):
                continue

            emp_name = alloc["employee"].get("name", "Unknown")
            proj_name = alloc["project"].get("name", "Unknown")

            text = (
                f"Allocation: {emp_name} on {proj_name}\n"
                f"Start: {alloc.get('startDate', 'N/A')}\n"
                f"End: {alloc.get('endDate', 'N/A')}"
            )

            metadata = {
                "source": "metric",
                "data_type": "allocation",
                "allocation_id": alloc["id"],
                "employee_id": alloc["employee"]["id"],
                "employee_name": emp_name,
                "project_id": alloc["project"]["id"],
                "project_name": proj_name,
                "synced_at": datetime.now(UTC).isoformat(),
            }

            texts.append(text)
            metadata_list.append(metadata)

        if texts:
            embeddings = embedding_provider.embed_batch(texts)
            await self._add_to_vector_store(
                vector_store, texts, embeddings, metadata_list
            )

        return len(texts)

    async def _add_to_vector_store(self, vector_store, texts, embeddings, metadata):
        """Add to vector store with Pinecone namespace support."""
        if not texts:
            return

        # Check if Pinecone (has namespace support)
        if hasattr(vector_store, "index") and vector_store.index is not None:
            # Use Pinecone namespace
            await self._add_to_pinecone_namespace(
                vector_store, texts, embeddings, metadata
            )
        else:
            # Elasticsearch: no namespace
            await vector_store.add_documents(texts, embeddings, metadata)

    async def _add_to_pinecone_namespace(
        self, vector_store, texts, embeddings, metadata
    ):
        """Add to Pinecone with 'metric' namespace."""
        import hashlib

        vectors = []
        for i, (text, emb) in enumerate(zip(texts, embeddings, strict=False)):
            doc_id = f"metric_{hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()}_{i}"
            meta = metadata[i] if metadata else {}
            meta["text"] = text
            vectors.append({"id": doc_id, "values": emb, "metadata": meta})

        # Upsert with namespace
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]

            def upsert_batch(b=batch):
                """Upsert Batch."""
                return vector_store.index.upsert(vectors=b, namespace="metric")

            await asyncio.get_event_loop().run_in_executor(None, upsert_batch)


async def main():
    """Main entry point."""
    runner = MetricSyncRunner()
    start_time = datetime.now(UTC)

    try:
        stats = await runner.run()

        duration = (datetime.now(UTC) - start_time).total_seconds()

        print("\n" + "=" * 60)
        print("📊 SYNC RESULTS:")
        print("=" * 60)
        print("✅ Status: SUCCESS")
        print(f"⏱️  Duration: {duration:.2f}s")
        print("\n📈 Records Synced:")
        print(f"   • Employees:   {stats['employees_synced']}")
        print(f"   • Projects:    {stats['projects_synced']}")
        print(f"   • Clients:     {stats['clients_synced']}")
        print(f"   • Allocations: {stats['allocations_synced']}")
        print("=" * 60)

    except Exception as e:
        duration = (datetime.now(UTC) - start_time).total_seconds()
        print("\n" + "=" * 60)
        print("📊 SYNC RESULTS:")
        print("=" * 60)
        print("❌ Status: FAILED")
        print(f"⏱️  Duration: {duration:.2f}s")
        print(f"💥 Error: {e}")
        print("=" * 60)
        raise


if __name__ == "__main__":
    asyncio.run(main())

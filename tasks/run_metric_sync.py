"""Manual script to run Metric.ai sync job."""

import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv  # noqa: E402

from config.settings import TasksSettings  # noqa: E402
from jobs.metric_sync import MetricSyncJob  # noqa: E402

# Load environment variables from root .env
root_env = Path(__file__).parent.parent / ".env"
load_dotenv(root_env)


async def main():
    """Run the Metric.ai sync job."""
    print("🚀 Starting Metric.ai sync job...")
    print(f"📄 Loaded environment from: {root_env}")

    # Create settings and job
    settings = TasksSettings()
    job = MetricSyncJob(
        settings,
        sync_employees=True,
        sync_projects=True,
        sync_clients=True,
        sync_allocations=True,
        allocations_start_year=2020,
    )

    # Execute the job
    result = await job.execute()

    print("\n" + "=" * 60)
    print("📊 SYNC RESULTS:")
    print("=" * 60)

    if result.get("status") == "success":
        job_result = result.get("result", {})
        print("✅ Status: SUCCESS")
        print(f"⏱️  Duration: {result.get('execution_time_seconds', 0):.2f}s")
        print("\n📈 Records Synced:")
        print(f"   • Employees:   {job_result.get('employees_synced', 0)}")
        print(f"   • Projects:    {job_result.get('projects_synced', 0)}")
        print(f"   • Clients:     {job_result.get('clients_synced', 0)}")
        print(f"   • Allocations: {job_result.get('allocations_synced', 0)}")

        if job_result.get("errors"):
            print(f"\n⚠️  Errors: {len(job_result['errors'])}")
            for error in job_result["errors"]:
                print(f"   - {error}")
    else:
        print("❌ Status: FAILED")
        print(f"⏱️  Duration: {result.get('execution_time_seconds', 0):.2f}s")
        print(f"💥 Error: {result.get('error', 'Unknown error')}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

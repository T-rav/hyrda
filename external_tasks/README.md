# External Tasks

This directory contains all scheduled tasks/jobs for the InsightMesh platform. Tasks are loaded dynamically at runtime without rebuilding the Docker image.

## Architecture

**Volume Mount Strategy:**
- Tasks are mounted externally: `./external_tasks:/app/external_tasks:ro`
- No tasks are baked into the Docker image
- Swap tasks by changing the volume mount
- Edit tasks without container rebuild

## Task Structure

Each task is a directory containing a `job.py` file:

```
external_tasks/
├── my_custom_task/
│   ├── job.py              # Required: Job class definition
│   ├── requirements.txt    # Optional: Additional dependencies
│   └── README.md           # Optional: Task documentation
└── another_task/
    └── job.py
```

## Creating a Task

### 1. Create Task Directory

```bash
mkdir -p external_tasks/my_task
```

### 2. Create `job.py`

The job file must contain a class that extends `BaseJob`:

```python
"""My Custom Task - Description of what this task does."""

import logging
from typing import Any

from jobs.base_job import BaseJob
from config.settings import TasksSettings

logger = logging.getLogger(__name__)


class MyTaskJob(BaseJob):
    """My custom task implementation."""

    # Metadata for task registry
    JOB_NAME = "My Custom Task"
    JOB_DESCRIPTION = "Does something useful on a schedule"

    # Parameter definitions for the UI
    REQUIRED_PARAMS = [
        {
            "name": "api_key",
            "label": "API Key",
            "type": "password",
            "description": "API key for external service"
        }
    ]

    OPTIONAL_PARAMS = [
        {
            "name": "batch_size",
            "label": "Batch Size",
            "type": "number",
            "default": 100,
            "description": "Number of items to process per batch"
        }
    ]

    def __init__(self, settings: TasksSettings, api_key: str, batch_size: int = 100):
        """Initialize the job."""
        super().__init__(settings)
        self.api_key = api_key
        self.batch_size = batch_size

    def get_job_id(self) -> str:
        """Return unique job ID for scheduling."""
        return "my_task"

    async def execute(self) -> dict[str, Any]:
        """
        Execute the task.

        Returns:
            Dict with standardized fields:
            - records_processed: Total items processed
            - records_success: Successful items
            - records_failed: Failed items
            - details: Additional info (optional)
        """
        logger.info(f"Starting my custom task (batch_size={self.batch_size})")

        try:
            # Your task logic here
            processed = 0
            success = 0
            failed = 0

            # Process items...
            for item in range(self.batch_size):
                try:
                    # Process item
                    success += 1
                except Exception as e:
                    logger.error(f"Failed to process item {item}: {e}")
                    failed += 1
                processed += 1

            return {
                "records_processed": processed,
                "records_success": success,
                "records_failed": failed,
                "details": "Custom task completed successfully"
            }

        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            raise


# Alias for dynamic loading (the loader looks for "Job" class)
Job = MyTaskJob
```

### 3. Optional: Add Dependencies

Create `requirements.txt` if your task needs additional packages:

```txt
requests>=2.31.0
pandas>=2.0.0
```

**Note:** Dependencies must be pre-installed in the Docker image or via init container.

## Built-in Tasks

### Google Drive Ingestion
- **Directory:** `gdrive_ingest/`
- **Purpose:** Ingest documents from Google Drive into vector database
- **Schedule:** Configurable (typically daily)

### Metric Sync
- **Directory:** `metric_sync/`
- **Purpose:** Sync employee metrics to internal systems
- **Schedule:** Configurable

### Portal Sync
- **Directory:** `portal_sync/`
- **Purpose:** Sync data with external portal
- **Schedule:** Configurable

### Slack User Import
- **Directory:** `slack_user_import/`
- **Purpose:** Import and sync Slack workspace users
- **Schedule:** Configurable

## Task Lifecycle

1. **Discovery:** Tasks are auto-discovered on service startup
2. **Registration:** Task metadata is registered with the scheduler
3. **Scheduling:** Tasks are scheduled via the Tasks UI
4. **Execution:** Scheduler runs tasks based on schedule
5. **Monitoring:** Task runs are tracked in the database

## Environment Variables

Configure the tasks service:

```bash
# External tasks path (set in docker-compose.yml)
EXTERNAL_TASKS_PATH=/app/external_tasks

# Task database
TASK_DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/insightmesh_task

# Data database (for task data storage)
DATA_DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/insightmesh_data
```

## Hot Reload (Development)

Tasks can be reloaded without restarting the container:

```python
from services.external_task_loader import reload_external_task

# Reload a specific task
reload_external_task("my_task")
```

## Deployment

### Single-Tenant Model

Each customer gets their own task volume mount:

```yaml
# Customer A docker-compose override
services:
  tasks:
    volumes:
      - ./customer-a-tasks:/app/external_tasks:ro
```

### Kubernetes

Use ConfigMaps or Volumes:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: custom-tasks
data:
  my_task.py: |
    # Task code here...
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: tasks
        volumeMounts:
        - name: custom-tasks
          mountPath: /app/external_tasks
          readOnly: true
      volumes:
      - name: custom-tasks
        configMap:
          name: custom-tasks
```

## Best Practices

1. **Idempotency:** Tasks should be safe to run multiple times
2. **Error Handling:** Always catch and log exceptions
3. **Standardized Returns:** Return consistent `records_*` fields
4. **Logging:** Use structured logging with task context
5. **Testing:** Test tasks before deploying to production
6. **Documentation:** Include README.md explaining the task

## Troubleshooting

### Task Not Loading

Check the logs:
```bash
docker logs insightmesh-tasks | grep "external_task_loader"
```

Common issues:
- Missing `job.py` file
- `Job` class not defined
- Import errors in task code
- Directory not mounted correctly

### Task Fails on Execute

Check TaskRun records in the database:
```sql
SELECT * FROM task_runs
WHERE status = 'failed'
ORDER BY started_at DESC
LIMIT 10;
```

## Support

For issues or questions:
- GitHub: https://github.com/your-org/insightmesh/issues
- Docs: https://docs.insightmesh.ai

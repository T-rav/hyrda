# InsightMesh - Tasks Service

A standalone APScheduler WebUI service for managing scheduled tasks in the InsightMesh ecosystem. This service provides a web interface for creating, managing, and monitoring scheduled jobs like Slack user imports and metrics collection.

## Features

- **Web-based Dashboard**: Modern, responsive web interface for job management
- **Multiple Job Types**:
  - Slack User Import: Synchronize Slack users to database
  - Metrics Collection: System and usage metrics aggregation
- **Flexible Scheduling**: Support for interval, cron, and one-time jobs
- **Real-time Monitoring**: Live job status updates and execution history
- **RESTful API**: Complete API for programmatic job management
- **Integration Ready**: Built to integrate with the main Slack bot service

## Quick Start

### 1. Environment Setup

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Tasks Service Configuration
TASKS_PORT=5001
TASKS_HOST=0.0.0.0
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_URL=sqlite:///tasks.db
REDIS_URL=redis://localhost:6379/2

# Main Slack Bot API (for integration)
SLACK_BOT_API_URL=http://localhost:8080
SLACK_BOT_API_KEY=your-api-key-here

# Slack API (for user import jobs)
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Run the Service

```bash
python app.py
```

The service will be available at:
- **Dashboard**: http://localhost:5001/
- **API**: http://localhost:5001/api/

## Job Types

### Slack User Import

Synchronizes Slack workspace users to a database via the main bot API.

**Parameters:**
- `workspace_filter` (optional): Filter by workspace
- `user_types` (optional): User types to include (member, admin, bot)
- `include_deactivated` (optional): Include deactivated users

**Schedule Examples:**
- Every hour: `{"trigger": "interval", "hours": 1}`
- Daily at 2 AM: `{"trigger": "cron", "hour": 2, "minute": 0}`


### Metrics Collection

Collects and aggregates system metrics from various sources.

**Parameters:**
- `metric_types` (optional): Types of metrics to collect (usage, performance, errors, slack)
- `time_range_hours` (optional): Time range for metric collection (default: 24)
- `aggregate_level` (optional): Aggregation level (hourly, daily)

**Schedule Examples:**
- Every 15 minutes: `{"trigger": "interval", "minutes": 15}`
- Hourly: `{"trigger": "interval", "hours": 1}`

## API Endpoints

### Scheduler Management

- `GET /api/scheduler/info` - Get scheduler status and information
- `GET /health` - Health check endpoint

### Job Management

- `GET /api/jobs` - List all jobs
- `POST /api/jobs` - Create a new job
- `GET /api/jobs/{job_id}` - Get job details
- `PUT /api/jobs/{job_id}` - Update job
- `DELETE /api/jobs/{job_id}` - Delete job
- `POST /api/jobs/{job_id}/pause` - Pause job
- `POST /api/jobs/{job_id}/resume` - Resume job

### Job Types

- `GET /api/job-types` - List available job types with parameters

## Creating Tasks via API

### Example: Create Slack User Import Task

```bash
curl -X POST http://localhost:5001/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "slack_user_import",
    "job_id": "daily_user_sync",
    "schedule": {
      "trigger": "cron",
      "hour": 2,
      "minute": 0
    },
    "parameters": {
      "user_types": "member,admin",
      "include_deactivated": false
    }
  }'
```


### Example: Create Metrics Collection Job

```bash
curl -X POST http://localhost:5001/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "metrics_collection",
    "schedule": {
      "trigger": "interval",
      "minutes": 30
    },
    "parameters": {
      "metric_types": "usage,performance,errors",
      "time_range_hours": 1,
      "aggregate_level": "hourly"
    }
  }'
```

## Web Interface

The web interface provides:

### Dashboard (`/`)
- Scheduler status and statistics
- Recent job activity
- Quick job actions (pause, resume, delete)
- Auto-refresh capability

### Tasks Management (`/tasks`)
- Complete job listing with details
- Create new jobs with form wizard
- Job details modal with full information
- Bulk job operations

## Database Storage

The service uses:
- **SQLAlchemy**: Primary job store for persistence
- **Redis**: Optional secondary job store for high-performance scenarios

Tasks are stored with full metadata including:
- Execution history
- Parameter validation
- Error tracking
- Performance metrics

## Integration with Main Bot

The tasks service integrates with the main Slack bot through HTTP APIs:

### User Import Integration
- Sends processed user data to `/api/users/import`
- Includes job metadata for tracking


### Metrics Integration
- Stores collected metrics via `/api/metrics/store`
- Retrieves metrics from `/api/metrics/{type}`

## Monitoring and Logging

### Health Checks
- `/health` endpoint for service monitoring
- Scheduler status validation
- Database connectivity verification

### Logging
- Structured logging with loguru
- Job execution tracking
- Error reporting with stack traces
- Performance metrics logging

### Metrics
- Job execution statistics
- Success/failure rates
- Execution time tracking
- Resource usage monitoring

## Security

### API Security
- Optional API key authentication
- Request validation and sanitization
- SQL injection prevention via SQLAlchemy

### Job Security
- Parameter validation before execution
- Sandbox execution environment
- Resource limits and timeouts
- Error handling and recovery

## Development

### Project Structure

```
tasks/
├── app.py                 # Main Flask application
├── config/
│   └── settings.py        # Configuration management
├── jobs/
│   ├── base_job.py        # Base job class
│   ├── job_registry.py    # Job type registry
│   ├── slack_user_import.py
│   └── metrics_collection.py
├── services/
│   └── scheduler_service.py
├── templates/             # Web UI templates
│   ├── base.html
│   ├── dashboard.html
│   └── tasks.html
├── tests/                 # Test suite
└── static/                # Static assets
```

### Adding New Job Types

1. Create a new job class extending `BaseJob`:

```python
from jobs.base_job import BaseJob

class CustomJob(BaseJob):
    JOB_NAME = "Custom Job"
    JOB_DESCRIPTION = "Description of what this job does"
    REQUIRED_PARAMS = ["required_param"]
    OPTIONAL_PARAMS = ["optional_param"]

    async def _execute_job(self) -> Dict[str, Any]:
        # Implement job logic
        return {"status": "completed"}
```

2. Register in `job_registry.py`:

```python
from .custom_job import CustomJob

class JobRegistry:
    def __init__(self, settings, scheduler_service):
        self.job_types = {
            # ... existing jobs
            "custom_job": CustomJob,
        }
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## Production Deployment

### Docker

Build and run with Docker:

```bash
docker build -t ai-slack-bot-tasks .
docker run -p 5001:5001 --env-file .env ai-slack-bot-tasks
```

### Systemd Service

Create `/etc/systemd/system/tasks-service.service`:

```ini
[Unit]
Description=InsightMesh Tasks Service
After=network.target

[Service]
Type=simple
User=taskuser
WorkingDirectory=/opt/tasks
Environment=PATH=/opt/tasks/venv/bin
ExecStart=/opt/tasks/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Environment Variables

Production environment considerations:

```bash
# Use PostgreSQL for production
DATABASE_URL=postgresql://user:pass@localhost/tasks

# Use Redis cluster for high availability
REDIS_URL=redis://redis-cluster:6379/0

# Enable production logging
FLASK_ENV=production
LOG_LEVEL=INFO

# Security
SECRET_KEY=your-very-secure-secret-key
SLACK_BOT_API_KEY=your-api-authentication-key
```

## Troubleshooting

### Common Issues

1. **Tasks not executing**
   - Check scheduler status at `/api/scheduler/info`
   - Verify database connectivity
   - Review job parameters and trigger configuration


3. **Slack API errors**
   - Validate bot tokens and permissions
   - Check Slack API rate limits
   - Verify workspace access

### Debug Mode

Run in debug mode for development:

```bash
FLASK_ENV=development python app.py
```

This enables:
- Detailed error messages
- Auto-reload on code changes
- Enhanced logging output

## License

This project is part of the InsightMesh ecosystem. See the main project repository for license information.

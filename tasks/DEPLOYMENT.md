# Tasks Service Deployment Guide

This guide covers deploying the APScheduler WebUI Tasks Service alongside your AI Slack Bot.

## Quick Start (Development)

1. **Navigate to tasks directory:**
   ```bash
   cd tasks
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install dependencies:**
   ```bash
   make install-dev
   ```

4. **Run the service:**
   ```bash
   make run
   ```

5. **Access the WebUI:**
   - Dashboard: http://localhost:5001/
   - Tasks: http://localhost:5001/tasks

## Production Deployment

### Option 1: Docker (Recommended)

1. **Create Dockerfile:**
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app
   COPY . .
   RUN pip install -e .

   EXPOSE 5001
   CMD ["python", "app.py"]
   ```

2. **Build and run:**
   ```bash
   make docker-build
   make docker-run
   ```

### Option 2: Systemd Service

1. **Create service file** `/etc/systemd/system/tasks-service.service`:
   ```ini
   [Unit]
   Description=AI Slack Bot Tasks Service
   After=network.target

   [Service]
   Type=simple
   User=taskuser
   WorkingDirectory=/opt/ai-slack-bot/tasks
   Environment=PATH=/opt/ai-slack-bot/tasks/venv/bin
   EnvironmentFile=/opt/ai-slack-bot/tasks/.env
   ExecStart=/opt/ai-slack-bot/tasks/venv/bin/python app.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

2. **Enable and start:**
   ```bash
   sudo systemctl enable tasks-service
   sudo systemctl start tasks-service
   ```

## Configuration

### Required Environment Variables

```bash
# Server Configuration
TASKS_PORT=5001
SECRET_KEY=your-secure-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost/tasks  # or sqlite:///tasks.db
REDIS_URL=redis://localhost:6379/2

# Main Bot Integration
SLACK_BOT_API_URL=http://localhost:8080
SLACK_BOT_API_KEY=your-api-key

# For Slack User Import Tasks
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# For Google Drive Ingest Tasks
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
GOOGLE_TOKEN_PATH=/path/to/token.json
```

### Optional Environment Variables

```bash
# External Metrics API
METRICS_API_URL=https://api.metrics.example.com
METRICS_API_KEY=your-metrics-api-key

# Scheduler Configuration
SCHEDULER_TIMEZONE=UTC
SCHEDULER_JOB_DEFAULTS_COALESCE=true
SCHEDULER_JOB_DEFAULTS_MAX_INSTANCES=1
SCHEDULER_EXECUTORS_THREAD_POOL_MAX_WORKERS=20
```

## Integration with Main Bot

The tasks service is designed to work alongside your main AI Slack Bot. The integration happens through HTTP API calls.

### 1. Start Main Bot

The main bot should be running with the health endpoints available on port 8080 (default).

### 2. Configure Integration

Set `SLACK_BOT_API_URL=http://localhost:8080` in your tasks service `.env` file.

### 3. Available Integration Endpoints

The main bot now provides these endpoints for the tasks service:

#### **POST /api/users/import**
Receives user data from Slack user import jobs.

#### **POST /api/ingest/completed**
Receives notifications when document ingestion completes.

#### **POST /api/metrics/store**
Receives aggregated metrics from metrics collection jobs.

#### **GET /api/metrics/{type}**
Provides metrics data for collection jobs.

## Creating Scheduled Tasks

### Via Web Interface

1. Go to http://localhost:5001/jobs
2. Click "Create Job"
3. Select job type and configure parameters
4. Set schedule (interval, cron, or one-time)
5. Click "Create Job"

### Via API

```bash
# Create a Slack user import job (daily at 2 AM)
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
      "user_types": ["member", "admin"],
      "include_deactivated": false
    }
  }'

# Create a Google Drive ingest job (every 6 hours)
curl -X POST http://localhost:5001/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "google_drive_ingest",
    "schedule": {
      "trigger": "interval",
      "hours": 6
    },
    "parameters": {
      "folder_id": "1ABC123DEF456GHI789",
      "metadata": "{\"department\": \"engineering\"}"
    }
  }'

# Create a metrics collection job (every 30 minutes)
curl -X POST http://localhost:5001/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "metrics_collection",
    "schedule": {
      "trigger": "interval",
      "minutes": 30
    },
    "parameters": {
      "metric_types": ["usage", "performance", "errors"],
      "time_range_hours": 1
    }
  }'
```

## Monitoring & Troubleshooting

### Health Check

```bash
curl http://localhost:5001/health
```

### View Job Status

```bash
# List all jobs
curl http://localhost:5001/api/jobs

# Get specific job details
curl http://localhost:5001/api/jobs/your-job-id

# Get scheduler info
curl http://localhost:5001/api/scheduler/info
```

### Logs

The service logs to stdout by default. In production:

```bash
# With systemd
sudo journalctl -u tasks-service -f

# With Docker
docker logs -f ai-slack-bot-tasks
```

### Common Issues

1. **Tasks not executing**
   - Check scheduler status: `curl http://localhost:5001/api/scheduler/info`
   - Verify database connectivity
   - Check job parameters

2. **Integration failures**
   - Verify main bot is running on configured URL
   - Check API key configuration
   - Review network connectivity

3. **Google Drive jobs failing**
   - Verify credentials file exists and is readable
   - Check folder ID and permissions
   - Ensure ingest service is available

## Performance Tuning

### Database

For production, use PostgreSQL instead of SQLite:

```bash
DATABASE_URL=postgresql://user:pass@localhost/tasks
```

### Redis

Use Redis cluster for high availability:

```bash
REDIS_URL=redis://redis-cluster:6379/0
```

### Scheduler Settings

Adjust based on load:

```bash
SCHEDULER_EXECUTORS_THREAD_POOL_MAX_WORKERS=50
SCHEDULER_JOB_DEFAULTS_MAX_INSTANCES=3
```

## Security Considerations

1. **API Keys**: Use strong, unique API keys for bot integration
2. **Network**: Restrict access to tasks service to necessary hosts
3. **Credentials**: Store Google credentials securely with proper file permissions
4. **Database**: Use encrypted connections for production databases

## Backup & Recovery

### Database Backup

```bash
# PostgreSQL
pg_dump tasks > tasks_backup.sql

# SQLite
cp tasks.db tasks_backup.db
```

### Job Configuration Export

The WebUI provides job export functionality through the API:

```bash
curl http://localhost:5001/api/jobs > jobs_backup.json
```

## Scaling

### Horizontal Scaling

The tasks service can be scaled horizontally by:

1. Using a shared PostgreSQL database
2. Using Redis for job coordination
3. Running multiple instances behind a load balancer
4. Ensuring only one instance handles each job (APScheduler handles this automatically)

### Vertical Scaling

For single-instance scaling:

1. Increase thread pool size
2. Add more memory for job history
3. Use SSD storage for faster job lookups

## Maintenance

### Regular Tasks

1. **Monitor job execution rates and failures**
2. **Clean up old job execution logs**
3. **Update dependencies regularly**
4. **Backup job configurations and results**

### Updates

```bash
# Update the tasks service
cd tasks
git pull
make install
sudo systemctl restart tasks-service
```

This completes the deployment guide for the APScheduler WebUI Tasks Service.

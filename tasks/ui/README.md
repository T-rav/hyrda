# Tasks Dashboard UI

A React-based dashboard for managing and monitoring scheduled tasks in the InsightMesh ecosystem.

## Features

- **Task Management**: Create, edit, pause, resume, and delete scheduled tasks
- **Real-time Monitoring**: Live updates of task status and execution history
- **Multiple Job Types**: Support for Slack user import, Google Drive ingestion, and metrics collection
- **Flexible Scheduling**: Interval, cron, and one-time job scheduling
- **Task Details**: Comprehensive view of task parameters and execution logs
- **Responsive Design**: Clean, mobile-friendly interface
- **Auto-refresh**: Automatic updates every 10 seconds

## Quick Start

```bash
# Install dependencies
cd tasks/ui
npm install

# Build for production
npm run build

# The tasks service will automatically serve the React app at:
# - http://localhost:5001/
# - http://localhost:5001/tasks
```

## Development

```bash
# Install dependencies
npm install

# Start development server (with API proxy)
npm run dev

# Build for production
npm run build
```

## Supported Task Types

### Slack User Import
- Synchronize Slack workspace users to database
- Configurable user types and filters
- Scheduled or one-time execution

### Google Drive Ingest
- Automated document ingestion from Google Drive folders
- Support for various document formats
- Metadata enrichment and force update options

### Metrics Collection
- System and usage metrics aggregation
- Configurable time ranges and aggregation levels
- Performance and error tracking

## API Integration

The dashboard connects to the tasks service API:

- `GET /api/jobs` - List all tasks
- `POST /api/jobs` - Create new task
- `PUT /api/jobs/{id}` - Update task
- `DELETE /api/jobs/{id}` - Delete task
- `POST /api/jobs/{id}/pause` - Pause task
- `POST /api/jobs/{id}/resume` - Resume task
- `GET /api/scheduler/info` - Scheduler status

## Architecture

- **React 18** with functional components and hooks
- **Vite** for fast development and building
- **Lucide React** for consistent icons
- **Custom hooks** for data fetching and state management
- **Error boundaries** for robust error handling
- **Responsive grid** layout

## Dashboard Features

### Task Overview
- **Active Tasks**: Currently running and scheduled tasks
- **Task History**: Execution history with success/failure tracking
- **Scheduler Status**: Real-time scheduler health and statistics

### Task Management
- **Create Tasks**: Form wizard for creating new scheduled tasks
- **Edit Tasks**: Modify existing task parameters and schedules
- **Bulk Operations**: Pause, resume, or delete multiple tasks
- **Task Details**: Comprehensive view of task configuration and logs

### Real-time Updates
- Auto-refresh every 10 seconds
- Manual refresh capability
- Live status indicators
- Error handling with fallback states

## Deployment

The built React app is automatically served by the tasks service. No additional web server required.

For production deployment, ensure the React app is built:

```bash
cd tasks/ui && npm run build
```

The tasks service will serve the built files from `tasks/ui/dist/`.

## Development Setup

1. **Start the tasks service**:
   ```bash
   cd tasks && python app.py
   ```

2. **Start the UI development server**:
   ```bash
   cd tasks/ui && npm run dev
   ```

3. **Access the dashboard**:
   - Production: http://localhost:5001/
   - Development: http://localhost:5173/

## Integration with Tasks Service

The UI integrates seamlessly with the tasks service backend:

- **Real-time Data**: Fetches live task data and scheduler status
- **Form Validation**: Client-side validation with server-side confirmation
- **Error Handling**: Comprehensive error display and recovery
- **State Management**: Optimistic updates with rollback on failure

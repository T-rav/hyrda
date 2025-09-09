# Health Dashboard UI

A React-based health monitoring dashboard for the AI Slack Bot.

## Features

- **Real-time Status Monitoring**: Live updates every 10 seconds
- **Service Health Checks**: Monitor LLM API, cache, metrics, and configuration
- **Responsive Design**: Works on desktop and mobile devices
- **Fallback Mode**: Simple HTML dashboard when React app isn't built
- **API Integration**: Connects to `/api/*` endpoints for health data

## Quick Start

### Option 1: Simple Fallback UI (No Build Required)

The health server automatically serves a fallback HTML dashboard at:
- `http://localhost:8080/`
- `http://localhost:8080/ui`

This provides basic health monitoring with auto-refresh functionality.

### Option 2: Full React Dashboard

For the enhanced React experience:

```bash
# Install dependencies
cd bot/health_ui
npm install

# Build for production
npm run build

# The health server will automatically serve the built React app
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

## API Endpoints

The dashboard connects to these health endpoints:

- `GET /api/health` - Basic system health
- `GET /api/ready` - Comprehensive readiness checks  
- `GET /api/metrics` - Application metrics (JSON)
- `GET /api/prometheus` - Prometheus metrics

## Architecture

- **React 18** with functional components and hooks
- **Vite** for fast development and building
- **Lucide React** for consistent icons
- **CSS Modules** for component styling
- **Auto-refresh** with error handling
- **Responsive grid** layout

## Monitoring Features

### System Status
- Application uptime and version
- Overall health status indicator

### Service Health
- **LLM API**: Connection status and model info
- **Cache**: Redis availability and conversation count
- **Langfuse**: Observability service status  
- **Metrics**: Prometheus metrics collection
- **Configuration**: Environment variable validation

### Real-time Updates
- Auto-refresh every 10 seconds
- Manual refresh button
- Error handling with fallback states
- Last update timestamp

## Deployment

The built React app is automatically served by the health server when available. No additional web server required.

For production deployment, ensure the React app is built:

```bash
cd bot/health_ui && npm run build
```

The health server will serve the built files from `bot/health_ui/dist/`.

# Health Dashboard UI

A React-based health monitoring dashboard for the AI Slack Bot.

## Features

- **Real-time Status Monitoring**: Live updates every 10 seconds with auto-refresh
- **Service Health Checks**: Monitor LLM API, cache, Langfuse, and metrics services
- **Big Metrics Display**: Prominent display of key metrics (memory usage, active conversations, uptime)
- **Dynamic Versioning**: Reads version directly from pyproject.toml
- **Responsive Design**: Clean, mobile-friendly interface
- **Smart Status Handling**: Shows metrics when healthy, error details when issues occur
- **API Integration**: Connects to comprehensive `/api/*` health endpoints

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
- **Application**: Version (dynamic from pyproject.toml) and health status
- **LLM API**: Provider and model information with connection status  
- **System Uptime**: Big, prominent uptime display with last update time

### Service Health
- **LLM API**: Connection status and model information
- **Cache**: Redis availability with memory usage metrics
- **Langfuse**: Observability service status and configuration
- **Metrics**: Prometheus metrics with active conversation count

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

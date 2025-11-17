# Control Plane Dockerfile - Multi-stage build for Flask API + React UI

# Stage 1: Build React UI
FROM node:18-alpine AS ui-builder

WORKDIR /app/ui

# Copy UI package files
COPY ui/package*.json ./

# Install dependencies
RUN npm ci --no-audit

# Copy UI source
COPY ui/ ./

# Build for production
RUN npm run build

# Stage 2: Python Flask API
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-mysql-client \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy control plane Python dependencies
COPY control_plane/pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy control plane application code
COPY control_plane/ ./

# Copy built React UI from stage 1
COPY --from=ui-builder /app/ui/dist ./ui/dist

# Create logs directory
RUN mkdir -p logs

# Expose port 6001
EXPOSE 6001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6001/api/health')"

# Run Flask app
CMD ["python", "-u", "app.py"]

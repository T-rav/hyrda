# Control Plane Dockerfile - Multi-stage build for Flask API + React UI

# Stage 1: Build React UI
FROM node:18-alpine AS ui-builder

WORKDIR /app/ui

# Copy UI package files
COPY control_plane/ui/package*.json ./

# Install dependencies
RUN npm ci --no-audit

# Copy UI source
COPY control_plane/ui/ ./

# Build for production
RUN npm run build

# Stage 2: Python Flask API
FROM python:3.11-slim

# Suppress debconf/Perl warnings during apt-get
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-mysql-client \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first
COPY shared/ /app/shared/

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
    CMD python -c "import urllib.request, ssl; urllib.request.urlopen('https://localhost:6001/health', context=ssl._create_unverified_context())"

# Run FastAPI app with Uvicorn with SSL
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "6001", "--workers", "4", "--ssl-keyfile", "ssl/localhost.key", "--ssl-certfile", "ssl/localhost.crt"]

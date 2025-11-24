# Stage 1: Build React UI
FROM node:20-alpine AS ui-builder
WORKDIR /app/health_ui
COPY health_ui/package*.json ./
RUN npm ci --no-audit
COPY health_ui/ ./
RUN npm run build

# Stage 2: Python application
FROM public.ecr.aws/docker/library/python:3.11-slim

# Use bash with pipefail
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install security updates
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Copy built UI from stage 1
COPY --from=ui-builder /app/health_ui/dist ./health_ui/dist

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production

# Expose dashboard port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Switch to non-root user
USER appuser

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

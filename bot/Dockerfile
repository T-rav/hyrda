# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim

# Use bash with pipefail for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install security updates and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    curl \
    default-mysql-client \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Copy application code first (needed for pyproject.toml to work)
COPY --chown=appuser:appuser . .

# Install Python dependencies from pyproject.toml with proper error logging
RUN set -eux \
    && pip install --no-cache-dir --upgrade pip wheel setuptools \
    && pip install --no-cache-dir -e . -vvv --log /tmp/pip_install.log \
    || { echo "=== PIP INSTALL FAILED ==="; cat /tmp/pip_install.log || true; exit 1; }

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO

# Expose health check port
EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Switch to non-root user
USER appuser

# Use exec form for better signal handling
CMD ["python", "-u", "app.py"]

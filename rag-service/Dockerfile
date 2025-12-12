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
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Copy shared library first (required for common utilities)
COPY --chown=appuser:appuser ./shared /app/shared

# Copy application code
COPY --chown=appuser:appuser ./rag-service /app

# Verify Python version and upgrade pip
RUN set -eux \
    && python --version \
    && pip --version \
    && pip install --no-cache-dir --upgrade pip wheel setuptools \
    && pip --version

# Install dependencies from requirements.txt
RUN set -x \
    && pip install --no-cache-dir -r requirements.txt 2>&1 | tee /tmp/pip_install.log; \
    if [ ${PIPESTATUS[0]} -ne 0 ]; then \
        echo "=== PIP INSTALL FAILED ==="; \
        echo "Python version: $(python --version)"; \
        echo "Pip version: $(pip --version)"; \
        echo "Last 100 lines of pip install log:"; \
        tail -100 /tmp/pip_install.log; \
        exit 1; \
    fi

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    PORT=8002

# Expose rag service port
EXPOSE 8002

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Switch to non-root user
USER appuser

# Run with Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8002", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

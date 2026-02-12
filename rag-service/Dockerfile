# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim

# Build arguments for versioning
ARG VERSION=0.0.0
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

# Use bash with pipefail for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install security updates and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    curl \
    ca-certificates \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Trust all self-signed certificates for inter-service communication (optional)
# Trust all self-signed certificates for inter-service communication
# SSL certificates are mounted as volumes at runtime via docker-compose.yml
# No need to copy during build - handled at runtime

# Copy shared library first (required for common utilities)
COPY --chown=appuser:appuser ./shared /app/shared

# Copy application code
# Copy version file from project root
COPY --chown=appuser:appuser .version /app/.version


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
    if [ "${PIPESTATUS[0]}" -ne 0 ]; then \
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
    PORT=8002 \
    APP_VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA} \
    BUILD_DATE=${BUILD_DATE}

# Add OCI labels for versioning
LABEL org.opencontainers.image.title="InsightMesh RAG Service" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}"

# Expose rag service port
EXPOSE 8002

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Switch to non-root user
USER appuser

# Run with Gunicorn for production
# Note: Empty forwarded-allow-ips disables proxy headers middleware (no X-Forwarded-* processing)
CMD ["gunicorn", "--bind", "0.0.0.0:8002", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120", "--forwarded-allow-ips", "", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

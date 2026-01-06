# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim

# Use bash with pipefail for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install security updates and build dependencies
# WeasyPrint requirements for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    curl \
    ca-certificates \
    libnss3-tools \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Install mkcert for locally-trusted SSL certificates
RUN curl -sL https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64 \
    -o /usr/local/bin/mkcert && \
    chmod +x /usr/local/bin/mkcert

# Set working directory
WORKDIR /app

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Copy shared library first
COPY --chown=appuser:appuser ./shared /app/shared

# Copy application code (needed for pyproject.toml to work)
# Copy version file from project root
COPY --chown=appuser:appuser .version /app/.version

COPY --chown=appuser:appuser ./agent-service /app

# Make startup script executable
RUN chmod +x /app/startup.sh

# Verify Python version and upgrade pip
RUN set -eux \
    && python --version \
    && pip --version \
    && pip install --no-cache-dir --upgrade pip wheel setuptools \
    && pip --version

# Install package with detailed logging
RUN set -x \
    && pip install --no-cache-dir -e . 2>&1 | tee /tmp/pip_install.log; \
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
    LOG_LEVEL=INFO

# Expose agent service port
EXPOSE 8000

# Add health check (HTTPS)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -k https://localhost:8000/health || exit 1

# Switch to non-root user
USER appuser

# Run startup script (generates SSL certs and starts Gunicorn with HTTPS)
CMD ["sh", "/app/startup.sh"]

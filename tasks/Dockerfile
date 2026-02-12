# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim

# Build arguments for versioning
ARG VERSION=0.0.0
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

# Install security updates and dependencies including nginx, ffmpeg, and Playwright requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    ca-certificates \
    default-mysql-client \
    nginx \
    supervisor \
    ffmpeg \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create logs and cache directories with proper permissions
RUN mkdir -p /app/logs /app/.edgar && \
    chown -R appuser:appuser /app

# Trust all self-signed certificates for inter-service communication
# SSL certificates are mounted as volumes at runtime via docker-compose.yml
# No need to copy during build - handled at runtime

# Copy tasks application code first (needed for pyproject.toml to work)
COPY --chown=appuser:appuser tasks/ .

# Copy shared utilities (needed for middleware, auth, etc.)
COPY --chown=appuser:appuser ./shared /app/shared

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    playwright install chromium --with-deps

# Setup nginx configuration (as root)
COPY tasks/nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Copy React UI build to nginx directory
COPY --chown=www-data:www-data tasks/ui/dist /usr/share/nginx/html

# Copy and setup startup script
COPY --chown=appuser:appuser tasks/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO \
    HOME=/app \
    EDGAR_LOCAL_DATA_DIR=/app/.edgar \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    APP_VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA} \
    BUILD_DATE=${BUILD_DATE}

# Add OCI labels for versioning
LABEL org.opencontainers.image.title="InsightMesh Tasks" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}"

# Expose nginx port
EXPOSE 5001

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -k https://localhost:5001/health || exit 1

# Copy supervisor configuration
COPY tasks/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Use supervisor to manage both nginx and FastAPI
# nosemgrep: dockerfile.security.missing-user.missing-user
# Note: Supervisor runs as root to manage nginx (www-data) and FastAPI (appuser)
# The actual services run as non-root users (see supervisord.conf)
CMD ["/usr/bin/supervisord"]

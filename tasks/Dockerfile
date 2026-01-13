# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim

# Install security updates and dependencies including nginx
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    ca-certificates \
    default-mysql-client \
    nginx \
    supervisor \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create logs and cache directories with proper permissions
RUN mkdir -p /app/logs /app/.edgar && \
    chown -R appuser:appuser /app

# Trust all self-signed certificates for inter-service communication (optional)
# Copy .ssl directory (may be empty in CI) and conditionally install any certs found
COPY .ssl /tmp/.ssl/
RUN if [ -n "$(ls -A /tmp/.ssl/*-cert.pem 2>/dev/null)" ]; then \
        cp /tmp/.ssl/*-cert.pem /usr/local/share/ca-certificates/ && \
        update-ca-certificates; \
    fi

# Copy tasks application code first (needed for pyproject.toml to work)
COPY --chown=appuser:appuser tasks/ .

# Copy shared utilities (needed for middleware, auth, etc.)
COPY --chown=appuser:appuser ./shared /app/shared

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Setup nginx configuration (as root)
COPY tasks/nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Copy React UI build to nginx directory
COPY --chown=www-data:www-data tasks/ui/dist /usr/share/nginx/html

# Copy and setup startup script
COPY --chown=appuser:appuser tasks/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    HOME=/app \
    EDGAR_LOCAL_DATA_DIR=/app/.edgar

# Expose nginx port
EXPOSE 5001

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -k https://localhost:5001/health || exit 1

# Copy supervisor configuration
COPY tasks/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Use supervisor to manage both nginx and FastAPI
CMD ["/usr/bin/supervisord"]

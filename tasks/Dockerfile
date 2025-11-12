# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim

# Install security updates and dependencies including nginx
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    default-mysql-client \
    nginx \
    supervisor \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create logs, cache, and auth directories with proper permissions
RUN mkdir -p /app/logs /app/.edgar /app/auth/gdrive_credentials && \
    chown -R appuser:appuser /app

# Copy application code first (needed for pyproject.toml to work)
COPY --chown=appuser:appuser . .

# Install Python dependencies from pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Setup nginx configuration (as root)
COPY nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Copy React UI build to nginx directory
COPY --chown=www-data:www-data ui/dist /usr/share/nginx/html

# Copy and setup startup script
COPY --chown=appuser:appuser start.sh /app/start.sh
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
    CMD curl -f http://localhost:5001/health || exit 1

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Use supervisor to manage both nginx and Flask
CMD ["/usr/bin/supervisord"]

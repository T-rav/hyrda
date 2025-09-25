# Use Python 3.11 slim image for smaller attack surface
FROM python:3.11-slim

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

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Install Python dependencies directly
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "apscheduler>=3.10.4" \
    "flask>=3.0.0" \
    "flask-cors>=4.0.0" \
    "tzlocal>=5.2" \
    "pytz>=2023.3" \
    "python-dotenv>=1.0.0" \
    "pydantic>=1.9.0" \
    "pydantic-settings>=2.0.0" \
    "requests>=2.28.0" \
    "aiohttp>=3.8.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "pymysql>=1.1.0" \
    "alembic>=1.13.0" \
    "google-api-python-client>=2.0.0" \
    "google-auth-httplib2>=0.1.0" \
    "google-auth-oauthlib>=1.0.0" \
    "slack-sdk>=3.35.0" \
    "loguru>=0.7.0"

# Copy application code
COPY --chown=appuser:appuser . .

# Setup nginx configuration (as root)
COPY nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Copy React UI build to nginx directory
COPY --chown=www-data:www-data ui/dist /usr/share/nginx/html

# Startup script no longer needed - using supervisor

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO

# Expose nginx port
EXPOSE 5001

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Use supervisor to manage both nginx and Flask
CMD ["/usr/bin/supervisord"]

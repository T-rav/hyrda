# Use Python 3.11 slim image for smaller attack surface
FROM ghcr.io/docker-library/python:3.11-slim

# Install security updates and dependencies
RUN apt-get update && apt-get install -y \
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

# Copy requirements and install dependencies
COPY --chown=appuser:appuser pyproject.toml ./

# Install Python dependencies directly from pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "slack-bolt>=1.23.0" \
    "slack-sdk>=3.35.0" \
    "aiohttp>=3.8.0" \
    "python-dotenv>=1.0.0" \
    "pydantic>=1.9.0" \
    "pydantic-settings>=2.0.0" \
    "loguru>=0.7.0" \
    "requests>=2.28.0" \
    "redis>=5.0.0" \
    "asyncpg>=0.29.0" \
    "aiomysql>=0.2.0" \
    "pymysql>=1.1.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "alembic>=1.13.0" \
    "openai>=1.35.0" \
    "anthropic>=0.25.0" \
    "sentence-transformers>=2.2.0" \
    "elasticsearch>=8.0.0,<9.0.0" \
    "pinecone>=3.0.0" \
    "cohere>=5.0.0" \
    "numpy>=1.24.0" \
    "langfuse>=3.3.0" \
    "slackify-markdown>=0.2.0" \
    "prometheus-client>=0.19.0"

# Copy application code
COPY --chown=appuser:appuser . .

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

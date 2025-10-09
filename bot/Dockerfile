# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim

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

# Copy application code first (needed for pyproject.toml to work)
COPY --chown=appuser:appuser . .

# Install Python dependencies from pyproject.toml
# Split into separate steps for better error visibility
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -e . --verbose

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

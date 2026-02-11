FROM python:3.11-slim

# Build arguments for versioning
ARG VERSION=0.0.0
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Add OCI labels for versioning
LABEL org.opencontainers.image.title="InsightMesh LangSmith Proxy" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8002/health').raise_for_status()"

# Expose port
EXPOSE 8002

# Run proxy
CMD ["python", "app.py"]

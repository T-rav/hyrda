"""Secure HTTP client utilities for internal microservice communication.

This module provides secure HTTP client configuration for service-to-service calls.

Security:
- Internal Docker network: Use HTTP (no TLS needed for trusted network)
- External calls: Use HTTPS with proper certificate validation
- Never use verify=False in production
"""
import os
import httpx
from typing import Optional


def get_secure_client(
    timeout: float = 10.0,
    verify: Optional[bool] = None
) -> httpx.AsyncClient:
    """Get a properly configured HTTP client for service-to-service calls.

    Args:
        timeout: Request timeout in seconds
        verify: TLS verification setting. If None, auto-determines based on environment:
            - Development: verify=False allowed (with warning)
            - Production: verify=True (or path to CA bundle)

    Returns:
        Configured httpx.AsyncClient

    Security:
    - For internal Docker network calls, use HTTP URLs (not HTTPS)
    - For external calls, always use HTTPS with proper verification
    - Development mode allows verify=False with warning
    - Production mode enforces proper TLS verification
    """
    env = os.getenv("ENVIRONMENT", "development").lower()

    # Auto-determine verify setting if not specified
    if verify is None:
        if env in ("production", "prod", "staging"):
            # Production: require proper TLS verification
            ca_bundle = os.getenv("INTERNAL_CA_BUNDLE")
            if ca_bundle and os.path.exists(ca_bundle):
                verify = ca_bundle  # Use internal CA bundle
            else:
                verify = True  # Use system CA bundle
        else:
            # Development: allow insecure for localhost/Docker
            verify = False

    # Warn if using insecure verification
    if verify is False:
        import logging
        logger = logging.getLogger(__name__)
        if env in ("production", "prod", "staging"):
            raise ValueError(
                "SECURITY: Cannot use verify=False in production! "
                "Use HTTP for internal Docker network or provide CA bundle."
            )
        logger.warning(
            "⚠️  Using verify=False for HTTP client (development only). "
            "For production, use HTTP URLs for internal calls or provide CA bundle."
        )

    return httpx.AsyncClient(timeout=timeout, verify=verify)


def should_use_https(url: str) -> bool:
    """Determine if URL should use HTTPS based on hostname.

    Args:
        url: URL to check

    Returns:
        True if HTTPS should be used, False if HTTP is acceptable

    Logic:
    - Internal Docker services: HTTP is fine (control_plane, agent_service, etc.)
    - localhost/127.0.0.1: HTTP is fine (development)
    - External hosts: HTTPS required
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    # Internal Docker service names
    internal_services = {
        "control_plane",
        "control-plane",
        "agent_service",
        "agent-service",
        "tasks",
        "rag_service",
        "rag-service",
        "bot",
        "localhost",
        "127.0.0.1",
    }

    return hostname.lower() not in internal_services


def get_internal_service_url(service_name: str, path: str = "") -> str:
    """Get properly formatted URL for internal service.

    Args:
        service_name: Service name (e.g., "control_plane", "agent_service")
        path: API path (e.g., "/api/agents")

    Returns:
        Properly formatted URL (HTTP for internal, HTTPS for external)

    Example:
        >>> get_internal_service_url("control_plane", "/api/agents")
        'http://control_plane:6001/api/agents'
    """
    # Map service names to ports (internal Docker network)
    service_ports = {
        "control_plane": "6001",
        "control-plane": "6001",
        "agent_service": "8000",
        "agent-service": "8000",
        "tasks": "5001",
        "rag_service": "8002",
        "rag-service": "8002",
    }

    port = service_ports.get(service_name.lower())
    if not port:
        raise ValueError(f"Unknown internal service: {service_name}")

    # Use HTTP for internal Docker network (no TLS needed)
    base_url = f"http://{service_name}:{port}"

    # Ensure path starts with /
    if path and not path.startswith("/"):
        path = f"/{path}"

    return f"{base_url}{path}"

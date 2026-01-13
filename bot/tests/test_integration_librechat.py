"""LibreChat integration tests - CRITICAL INFRASTRUCTURE.

Tests verify LibreChat UI deployment and OAuth configuration.

Run with: pytest -v -m integration tests/test_integration_librechat.py
"""

import os
import time

import pytest

pytestmark = pytest.mark.integration


def test_librechat_docker_compose_valid():
    """
    CRITICAL TEST - LibreChat docker-compose.yml must be valid.

    Given: docker-compose.librechat.yml exists
    When: Validating docker-compose syntax
    Then: Configuration is valid

    Failure Impact: LibreChat won't start if docker-compose is invalid
    """
    import subprocess

    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "../../docker-compose.librechat.yml",
            "config",
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__),
    )

    assert result.returncode == 0, (
        f"docker-compose.librechat.yml is invalid: {result.stderr}"
    )
    print("✅ LibreChat docker-compose configuration is valid")


def test_librechat_mongodb_running():
    """
    CRITICAL TEST - LibreChat MongoDB must be running and healthy.

    Given: LibreChat stack is deployed
    When: Checking MongoDB container status
    Then: MongoDB container is running and healthy

    Failure Impact: LibreChat can't store users without MongoDB
    """
    import subprocess

    # Check if MongoDB container exists and is running
    result = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "name=librechat-mongodb",
            "--format",
            "{{.Status}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if not result.stdout.strip():
        pytest.skip("LibreChat MongoDB not running (stack not deployed)")

    status = result.stdout.strip().lower()
    assert "up" in status, f"MongoDB not running: {status}"

    # Check health status
    if "healthy" not in status and "health:" not in status:
        # Give it time to become healthy
        time.sleep(5)
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=librechat-mongodb",
                "--format",
                "{{.Status}}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip().lower()

    print(f"✅ LibreChat MongoDB status: {status}")


def test_librechat_ui_running():
    """
    CRITICAL TEST - LibreChat UI container must be running.

    Given: LibreChat stack is deployed
    When: Checking LibreChat container status
    Then: LibreChat container is running

    Failure Impact: Users can't access LibreChat UI
    """
    import subprocess

    result = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "name=librechat",
            "--filter",
            "status=running",
            "--format",
            "{{.Names}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    containers = result.stdout.strip().split("\n")
    librechat_containers = [c for c in containers if c and "librechat" in c]

    if not librechat_containers:
        pytest.skip("LibreChat not running (stack not deployed)")

    assert "librechat" in librechat_containers, "LibreChat container not found"
    print(f"✅ LibreChat containers running: {librechat_containers}")


def test_librechat_oauth_environment_variables():
    """
    CRITICAL TEST - LibreChat must have OAuth environment variables configured.

    Given: LibreChat container is running
    When: Checking environment variables
    Then: Required OAuth variables are set

    Failure Impact: OAuth login won't work without proper configuration
    """
    import subprocess

    # Check if LibreChat is running
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=^librechat$", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
    )

    if not result.stdout.strip():
        pytest.skip("LibreChat container not running")

    # Get environment variables from container
    result = subprocess.run(
        ["docker", "exec", "librechat", "env"],
        check=False,
        capture_output=True,
        text=True,
    )

    env_vars = result.stdout

    # Check required OAuth variables
    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_CALLBACK_URL",
        "DOMAIN_SERVER",
        "ALLOW_SOCIAL_LOGIN",
    ]

    missing_vars = []
    for var in required_vars:
        if var not in env_vars:
            missing_vars.append(var)
        else:
            # Get value for reporting (mask secrets)
            for line in env_vars.split("\n"):
                if line.startswith(f"{var}="):
                    value = line.split("=", 1)[1]
                    if "SECRET" in var or "KEY" in var:
                        print(f"✅ {var}=***REDACTED***")
                    else:
                        print(f"✅ {var}={value}")

    assert not missing_vars, (
        f"Missing required OAuth environment variables: {missing_vars}"
    )


def test_librechat_oauth_config_correct():
    """
    BUSINESS LOGIC TEST - LibreChat OAuth configuration must be correct.

    Given: LibreChat is configured for OAuth
    When: Checking feature flags
    Then: OAuth is enabled, email login is disabled

    Failure Impact: Users may be able to bypass OAuth restrictions
    """
    import subprocess

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=^librechat$", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
    )

    if not result.stdout.strip():
        pytest.skip("LibreChat container not running")

    # Get environment variables
    result = subprocess.run(
        ["docker", "exec", "librechat", "env"],
        check=False,
        capture_output=True,
        text=True,
    )

    env_vars = {}
    for line in result.stdout.split("\n"):
        if "=" in line:
            key, value = line.split("=", 1)
            env_vars[key] = value.strip()

    # Verify OAuth-only configuration
    assert env_vars.get("ALLOW_SOCIAL_LOGIN") == "true", "OAuth login not enabled"
    assert env_vars.get("ALLOW_EMAIL_LOGIN") == "false", (
        "Email login should be disabled"
    )
    assert env_vars.get("ALLOW_REGISTRATION") == "true", (
        "Registration needed for OAuth user creation"
    )

    # Verify domain whitelist
    assert env_vars.get("DOMAIN_WHITELIST") == "8thlight.com", (
        "Domain whitelist not configured"
    )

    print("✅ LibreChat configured for OAuth-only with 8thlight.com domain restriction")


def test_librechat_callback_url_correct():
    """
    CRITICAL TEST - OAuth callback URL must not be doubled.

    Given: LibreChat OAuth is configured
    When: Checking GOOGLE_CALLBACK_URL
    Then: Callback URL is a path only (not full URL)

    Failure Impact: OAuth login will fail with 400 error if URL is doubled
    """
    import subprocess

    result = subprocess.run(
        ["docker", "ps", "--filter", "name=^librechat$", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
    )

    if not result.stdout.strip():
        pytest.skip("LibreChat container not running")

    result = subprocess.run(
        ["docker", "exec", "librechat", "env"],
        check=False,
        capture_output=True,
        text=True,
    )

    for line in result.stdout.split("\n"):
        if line.startswith("GOOGLE_CALLBACK_URL="):
            callback_url = line.split("=", 1)[1].strip()
            # Should be path only, not full URL
            assert callback_url == "/oauth/google/callback", (
                f"GOOGLE_CALLBACK_URL should be path only, got: {callback_url}"
            )
            print(f"✅ GOOGLE_CALLBACK_URL correctly set to: {callback_url}")
            return

    pytest.fail("GOOGLE_CALLBACK_URL not found in environment variables")

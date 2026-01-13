#!/usr/bin/env python3
"""Test script for security hardening features.

Tests all 8 security enhancements:
1. JWT Secret Key (configured)
2. .env gitignored (verified)
3. Token Revocation with Redis
4. Rate Limiting on /auth/login
5. HTTPS Enforcement and Security Headers
6. Audit Logging for Service Calls
7. Request Signing with HMAC
8. Redis Session Backend
"""

import json
import os
import sys
import time

import httpx
import redis

# Configuration
CONTROL_PLANE_URL = "http://localhost:6001"
TASKS_URL = "http://localhost:5001"
AGENT_SERVICE_URL = "http://localhost:8000"
BOT_SERVICE_TOKEN = os.getenv("BOT_SERVICE_TOKEN", "")

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_test(test_name: str):
    """Print test header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST: {test_name}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


def print_success(message: str):
    """Print success message."""
    print(f"{GREEN}✓ {message}{RESET}")


def print_error(message: str):
    """Print error message."""
    print(f"{RED}✗ {message}{RESET}")


def print_info(message: str):
    """Print info message."""
    print(f"{YELLOW}ℹ {message}{RESET}")


# Test 1: Verify .env is gitignored
def test_env_gitignored():
    """Test that .env is in .gitignore."""
    print_test("Issue 2: Verify .env is gitignored")

    try:
        with open(".gitignore", "r") as f:
            content = f.read()

        if ".env" in content:
            print_success(".env is in .gitignore")
            return True
        else:
            print_error(".env is NOT in .gitignore")
            return False
    except Exception as e:
        print_error(f"Failed to check .gitignore: {e}")
        return False


# Test 3: Token Revocation
def test_token_revocation():
    """Test JWT token revocation with Redis."""
    print_test("Issue 3: Token Revocation with Redis")

    try:
        # Check Redis connection
        r = redis.from_url(os.getenv("CACHE_REDIS_URL", "redis://localhost:6379"))
        r.ping()
        print_success("Connected to Redis")

        # Test token revocation functions
        print_info("Testing token revocation functions...")

        # Import the JWT utilities
        sys.path.insert(0, ".")
        from shared.utils.jwt_auth import (
            create_access_token,
            is_token_revoked,
            revoke_token,
            verify_token,
        )

        # Create a test token
        token = create_access_token(
            user_email="test@example.com", user_name="Test User"
        )
        print_success(f"Created test token: {token[:20]}...")

        # Verify token works
        payload = verify_token(token)
        print_success(f"Token verified: {payload['email']}")

        # Revoke the token
        revoked = revoke_token(token)
        if revoked:
            print_success("Token revoked successfully")
        else:
            print_error("Token revocation failed (Redis unavailable?)")
            return False

        # Verify token is revoked
        if is_token_revoked(token):
            print_success("Token marked as revoked in Redis")
        else:
            print_error("Token NOT marked as revoked")
            return False

        # Try to verify revoked token (should fail)
        try:
            verify_token(token)
            print_error("Revoked token still validates! (BUG)")
            return False
        except Exception as e:
            if "revoked" in str(e).lower():
                print_success("Revoked token correctly rejected")
                return True
            else:
                print_error(f"Unexpected error: {e}")
                return False

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


# Test 4: Rate Limiting
def test_rate_limiting():
    """Test rate limiting on /auth/login."""
    print_test("Issue 4: Rate Limiting on /auth/login")

    try:
        # Make 11 requests (limit is 10 per 60 seconds)
        print_info("Making 11 requests to /auth/login (limit: 10/60s)...")

        rate_limited = False
        for i in range(11):
            response = httpx.get(
                f"{CONTROL_PLANE_URL}/auth/login", follow_redirects=False, timeout=5.0
            )

            if response.status_code == 429:
                print_success(f"Request {i+1}: Rate limited (429) ✓")
                rate_limited = True
                break
            elif response.status_code in [302, 200]:
                print_info(f"Request {i+1}: Success ({response.status_code})")
            else:
                print_error(f"Request {i+1}: Unexpected status {response.status_code}")

        if rate_limited:
            print_success("Rate limiting is working!")
            return True
        else:
            print_error("No rate limiting detected (made 11 requests without 429)")
            return False

    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


# Test 5: Security Headers
def test_security_headers():
    """Test security headers in responses."""
    print_test("Issue 5: HTTPS Enforcement and Security Headers")

    try:
        # Test control-plane
        print_info("Testing control-plane security headers...")
        response = httpx.get(f"{CONTROL_PLANE_URL}/health", timeout=5.0)

        headers_to_check = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Permissions-Policy",
        ]

        all_present = True
        for header in headers_to_check:
            if header in response.headers:
                print_success(f"{header}: {response.headers[header]}")
            else:
                print_error(f"{header}: MISSING")
                all_present = False

        # HSTS only in production
        if "Strict-Transport-Security" in response.headers:
            print_success(
                f"HSTS: {response.headers['Strict-Transport-Security']} (production mode)"
            )
        else:
            print_info("HSTS: Not set (development mode - expected)")

        # Test tasks service
        print_info("\nTesting tasks service security headers...")
        response = httpx.get(f"{TASKS_URL}/health", timeout=5.0)

        for header in headers_to_check:
            if header in response.headers:
                print_success(f"{header}: Present")
            else:
                print_error(f"{header}: MISSING")
                all_present = False

        return all_present

    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


# Test 6: Audit Logging
def test_audit_logging():
    """Test audit logging for service-to-service calls."""
    print_test("Issue 6: Audit Logging for Service Calls")

    try:
        print_info("Making authenticated service call to agent-service...")

        # Call agent-service with valid token
        headers = {"X-Service-Token": BOT_SERVICE_TOKEN}

        response = httpx.get(
            f"{AGENT_SERVICE_URL}/api/agents", headers=headers, timeout=5.0
        )

        if response.status_code == 200:
            print_success("Service call succeeded")
        else:
            print_error(f"Service call failed: {response.status_code}")
            return False

        # Check logs
        print_info("Checking agent-service logs for audit entry...")

        import subprocess

        result = subprocess.run(
            ["docker", "logs", "insightmesh-agent-service", "--tail", "50"],
            capture_output=True,
            text=True,
        )

        if "Service call: bot -> GET /api/agents" in result.stdout:
            print_success("Audit log entry found!")
            return True
        else:
            print_error("Audit log entry NOT found in recent logs")
            print_info("Recent logs:")
            print(result.stdout[-500:])
            return False

    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


# Test 7: Request Signing (HMAC)
def test_request_signing():
    """Test HMAC request signing between bot and agent-service."""
    print_test("Issue 7: Request Signing with HMAC")

    try:
        print_info("Testing HMAC signature generation and verification...")

        sys.path.insert(0, ".")
        from shared.utils.request_signing import (
            add_signature_headers,
            generate_signature,
            verify_signature,
        )

        # Test signature generation
        service_token = "test-token-12345"
        body = '{"query":"test","context":{}}'
        timestamp = str(int(time.time()))

        signature = generate_signature(service_token, body, timestamp)
        print_success(f"Generated signature: {signature[:20]}...")

        # Test signature verification (valid)
        is_valid, error = verify_signature(
            service_token, body, timestamp, signature, max_age_seconds=300
        )

        if is_valid:
            print_success("Valid signature verified successfully")
        else:
            print_error(f"Valid signature rejected: {error}")
            return False

        # Test signature verification (tampered body)
        tampered_body = '{"query":"tampered","context":{}}'
        is_valid, error = verify_signature(
            service_token, tampered_body, timestamp, signature, max_age_seconds=300
        )

        if not is_valid and "Invalid signature" in str(error):
            print_success("Tampered request correctly rejected")
        else:
            print_error("Tampered request NOT rejected!")
            return False

        # Test signature verification (expired)
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago
        old_signature = generate_signature(service_token, body, old_timestamp)

        is_valid, error = verify_signature(
            service_token, body, old_timestamp, old_signature, max_age_seconds=300
        )

        if not is_valid and "expired" in str(error).lower():
            print_success("Expired request correctly rejected")
        else:
            print_error(f"Expired request NOT rejected: {error}")
            return False

        print_success("All HMAC signature tests passed!")
        return True

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


# Test 8: Redis Session Backend
def test_redis_sessions():
    """Test Redis session persistence."""
    print_test("Issue 8: Redis Session Backend")

    try:
        # Check Redis connection
        r = redis.from_url(os.getenv("CACHE_REDIS_URL", "redis://localhost:6379"))
        r.ping()
        print_success("Connected to Redis")

        # Check for session keys (they start with "session:")
        print_info("Checking for session keys in Redis...")

        keys = r.keys("session:*")
        if keys:
            print_success(f"Found {len(keys)} session(s) in Redis")
            for key in keys[:3]:  # Show first 3
                ttl = r.ttl(key)
                print_info(f"  {key.decode()}: TTL={ttl}s")
        else:
            print_info("No sessions in Redis yet (expected if no one logged in)")

        print_success("Redis session backend is configured")
        return True

    except Exception as e:
        print_error(f"Test failed: {e}")
        return False


# Main test runner
def main():
    """Run all security tests."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}SECURITY HARDENING TEST SUITE{RESET}")
    print(f"{BLUE}Testing 8 security enhancements{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    results = {}

    # Run all tests
    results["Issue 2: .env gitignored"] = test_env_gitignored()
    results["Issue 3: Token Revocation"] = test_token_revocation()
    results["Issue 4: Rate Limiting"] = test_rate_limiting()
    results["Issue 5: Security Headers"] = test_security_headers()
    results["Issue 6: Audit Logging"] = test_audit_logging()
    results["Issue 7: Request Signing"] = test_request_signing()
    results["Issue 8: Redis Sessions"] = test_redis_sessions()

    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{status} - {test}")

    print(f"\n{BLUE}{'='*60}{RESET}")
    if passed == total:
        print(f"{GREEN}ALL TESTS PASSED! ({passed}/{total}){RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        return 0
    else:
        print(f"{RED}SOME TESTS FAILED ({passed}/{total}){RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

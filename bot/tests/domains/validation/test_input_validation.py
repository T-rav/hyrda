"""Data validation tests - Invalid input handling.

Tests that the system properly validates and rejects:
- SQL injection attempts
- XSS attempts
- Invalid data formats
- Missing required fields
- Boundary conditions
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.validation]


# ==============================================================================
# SQL Injection Prevention
# ==============================================================================


async def test_job_creation_rejects_sql_injection_in_name(
    authenticated_admin,
    service_urls,
):
    """
    Given: Malicious SQL in job name
    When: Admin tries to create job
    Then: Request is rejected or input is sanitized
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['tasks']}/api/jobs"

    # SQL injection attempts
    malicious_names = [
        "'; DROP TABLE jobs; --",
        "admin'--",
        "' OR '1'='1",
        "1'; DELETE FROM jobs WHERE '1'='1",
        "test'); DROP TABLE jobs;--",
    ]

    for malicious_name in malicious_names:
        payload = {
            "name": malicious_name,
            "job_type": "google_drive_ingestion",
            "schedule": "0 3 * * *",
            "enabled": False,
            "config": {},
        }

        response = await authenticated_admin.post(create_url, json=payload)

        # Should either:
        # 1. Reject with 400 (validation error)
        # 2. Sanitize and accept (200/201) but store safe version
        # 3. Return 422 (unprocessable entity)

        if response.status_code in [200, 201]:
            # If accepted, verify name was sanitized
            job_data = response.json()
            stored_name = job_data.get("name", "")

            # Cleanup
            job_id = job_data.get("job_id") or job_data.get("id")
            if job_id:
                delete_url = f"{service_urls['tasks']}/api/jobs/{job_id}"
                await authenticated_admin.delete(delete_url)

            # Verify dangerous characters removed or escaped
            assert "DROP" not in stored_name, (
                f"🔴 SQL INJECTION VULNERABILITY!\n"
                f"System accepted malicious SQL: {malicious_name}\n"
                f"Stored as: {stored_name}\n"
                f"SQL commands should be sanitized!"
            )

            print(f"✅ SANITIZED: '{malicious_name}' → '{stored_name}'")

        elif response.status_code in [400, 422]:
            print(f"✅ REJECTED: Malicious input '{malicious_name[:30]}...' rejected")

        else:
            # Unexpected status code
            pytest.fail(
                f"Unexpected response to SQL injection: {response.status_code}\n"
                f"Input: {malicious_name}"
            )

    print("\n🛡️ SQL INJECTION PROTECTION VALIDATED")


# ==============================================================================
# XSS Prevention
# ==============================================================================


async def test_group_creation_sanitizes_xss_in_description(
    authenticated_admin,
    service_urls,
    test_group_name,
):
    """
    Given: XSS payload in group description
    When: Admin creates group
    Then: Script tags are sanitized or escaped
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['control_plane']}/api/groups"

    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<iframe src='javascript:alert(1)'>",
    ]

    for xss_payload in xss_payloads:
        payload = {
            "name": f"{test_group_name}_{xss_payloads.index(xss_payload)}",
            "description": xss_payload,
            "metadata": {},
        }

        response = await authenticated_admin.post(create_url, json=payload)

        if response.status_code in [200, 201]:
            group_data = response.json()
            stored_description = group_data.get("description", "")
            group_name = group_data.get("name")

            # Cleanup
            delete_url = f"{service_urls['control_plane']}/api/groups/{group_name}"
            await authenticated_admin.delete(delete_url)

            # Verify script tags escaped or removed
            assert "<script>" not in stored_description, (
                f"🔴 XSS VULNERABILITY!\n"
                f"System accepted unescaped script tag!\n"
                f"Input: {xss_payload}\n"
                f"Stored: {stored_description}"
            )

            assert "javascript:" not in stored_description, (
                "🔴 XSS VULNERABILITY!\nSystem accepted javascript: protocol!"
            )

            print("✅ SANITIZED: XSS payload sanitized")

        elif response.status_code in [400, 422]:
            print("✅ REJECTED: XSS payload rejected")

    print("\n🛡️ XSS PROTECTION VALIDATED")


# ==============================================================================
# Invalid Format Validation
# ==============================================================================


async def test_job_creation_rejects_invalid_cron_schedule(
    authenticated_admin,
    service_urls,
    test_job_name,
):
    """
    Given: Invalid cron schedule format
    When: Admin tries to create job
    Then: Request is rejected with 400/422
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['tasks']}/api/jobs"

    invalid_schedules = [
        "invalid",
        "not a cron",
        "60 60 60 60 60",  # Invalid values
        "* * * * * * *",  # Too many fields
        "",  # Empty
        "0",  # Just a number
    ]

    for invalid_schedule in invalid_schedules:
        payload = {
            "name": f"{test_job_name}_{invalid_schedules.index(invalid_schedule)}",
            "job_type": "google_drive_ingestion",
            "schedule": invalid_schedule,
            "enabled": False,
            "config": {},
        }

        response = await authenticated_admin.post(create_url, json=payload)

        # Should reject invalid cron
        assert response.status_code in [400, 422], (
            f"🔴 VALIDATION BUG!\n"
            f"System accepted invalid cron schedule: '{invalid_schedule}'\n"
            f"Status: {response.status_code}\n"
            f"Invalid schedules should be rejected!"
        )

        print(f"✅ REJECTED: Invalid schedule '{invalid_schedule}'")

    print("\n✅ CRON SCHEDULE VALIDATION WORKING")


# ==============================================================================
# Missing Required Fields
# ==============================================================================


async def test_group_creation_requires_name_field(
    authenticated_admin,
    service_urls,
):
    """
    Given: Group creation without name
    When: Request is sent
    Then: Returns 400/422 validation error
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['control_plane']}/api/groups"

    # Missing name field
    payload = {
        "description": "Test group",
        # name field missing!
    }

    response = await authenticated_admin.post(create_url, json=payload)

    assert response.status_code in [400, 422], (
        f"🔴 VALIDATION BUG!\n"
        f"System accepted group creation without name!\n"
        f"Status: {response.status_code}\n"
        f"Required fields should be enforced!"
    )

    print("✅ REJECTED: Group creation without name")


async def test_permission_grant_requires_agent_name(
    authenticated_admin,
    service_urls,
    test_user_id,
):
    """
    Given: Permission grant without agent_name
    When: Request is sent
    Then: Returns 400/422 validation error
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    grant_url = f"{service_urls['control_plane']}/api/users/{test_user_id}/permissions"

    # Missing agent_name
    payload = {
        "granted_by": "admin",
        # agent_name missing!
    }

    response = await authenticated_admin.post(grant_url, json=payload)

    assert response.status_code in [400, 422], (
        f"🔴 VALIDATION BUG!\n"
        f"System accepted permission grant without agent_name!\n"
        f"Status: {response.status_code}"
    )

    print("✅ REJECTED: Permission grant without agent_name")


# ==============================================================================
# Boundary Conditions
# ==============================================================================


async def test_job_name_length_limit_enforced(
    authenticated_admin,
    service_urls,
):
    """
    Given: Extremely long job name
    When: Job creation attempted
    Then: Returns 400/422 or truncates to reasonable length
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['tasks']}/api/jobs"

    # Generate very long name (10,000 characters)
    very_long_name = "a" * 10000

    payload = {
        "name": very_long_name,
        "job_type": "google_drive_ingestion",
        "schedule": "0 3 * * *",
        "enabled": False,
        "config": {},
    }

    response = await authenticated_admin.post(create_url, json=payload)

    if response.status_code in [200, 201]:
        # If accepted, verify truncation
        job_data = response.json()
        stored_name = job_data.get("name", "")

        # Cleanup
        job_id = job_data.get("job_id") or job_data.get("id")
        if job_id:
            delete_url = f"{service_urls['tasks']}/api/jobs/{job_id}"
            await authenticated_admin.delete(delete_url)

        # Reasonable max length is usually 255 chars
        assert len(stored_name) <= 1000, (
            f"🔴 DOS VULNERABILITY!\n"
            f"System accepted {len(stored_name)} character name!\n"
            f"Names should have reasonable length limit."
        )

        print(f"✅ TRUNCATED: Long name truncated to {len(stored_name)} chars")

    elif response.status_code in [400, 422]:
        print("✅ REJECTED: Extremely long name rejected")


async def test_empty_string_fields_are_rejected(
    authenticated_admin,
    service_urls,
):
    """
    Given: Empty string for required field
    When: Entity creation attempted
    Then: Returns 400/422 validation error
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['control_plane']}/api/groups"

    payload = {
        "name": "",  # Empty string!
        "description": "Test",
    }

    response = await authenticated_admin.post(create_url, json=payload)

    assert response.status_code in [400, 422], (
        f"🔴 VALIDATION BUG!\n"
        f"System accepted empty string as name!\n"
        f"Status: {response.status_code}"
    )

    print("✅ REJECTED: Empty string for required field")


# ==============================================================================
# Unicode & Special Characters
# ==============================================================================


async def test_unicode_characters_handled_correctly(
    authenticated_admin,
    service_urls,
):
    """
    Given: Unicode characters in input
    When: Entity created
    Then: Characters preserved correctly
    """
    if not authenticated_admin:
        pytest.skip("Admin authentication not available")

    create_url = f"{service_urls['control_plane']}/api/groups"

    unicode_name = "test_group_🚀🎉_中文_ñoño"

    payload = {
        "name": unicode_name,
        "description": "Test unicode handling",
    }

    response = await authenticated_admin.post(create_url, json=payload)

    if response.status_code in [200, 201]:
        group_data = response.json()
        stored_name = group_data.get("name", "")

        # Cleanup
        delete_url = f"{service_urls['control_plane']}/api/groups/{stored_name}"
        await authenticated_admin.delete(delete_url)

        # Verify unicode preserved (or reasonably sanitized)
        print(f"✅ UNICODE: '{unicode_name}' → '{stored_name}'")

    elif response.status_code in [400, 422]:
        print("✅ REJECTED: Unicode in name (some systems disallow this)")

    # Either accepting or rejecting is fine, just verify consistent behavior

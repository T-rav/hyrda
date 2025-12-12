"""Debug auth fixture."""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_auth_fixture_debug(
    authenticated_user, authenticated_admin, service_urls
):
    """Debug test to verify auth fixtures work."""
    print(f"\n\nDEBUG authenticated_user type: {type(authenticated_user)}")
    print(
        f"DEBUG authenticated_user headers: {authenticated_user.headers if hasattr(authenticated_user, 'headers') else 'NO HEADERS'}"
    )

    print(f"\nDEBUG authenticated_admin type: {type(authenticated_admin)}")
    print(
        f"DEBUG authenticated_admin headers: {authenticated_admin.headers if hasattr(authenticated_admin, 'headers') else 'NO HEADERS'}"
    )

    # Try a request
    response = await authenticated_admin.get(
        f"{service_urls['control_plane']}/api/groups"
    )
    print(f"\nDEBUG Admin groups request: {response.status_code}")
    print(f"DEBUG Response: {response.text[:200]}")

    response2 = await authenticated_user.get(
        f"{service_urls['control_plane']}/api/groups"
    )
    print(f"\nDEBUG User groups request: {response2.status_code}")
    print(f"DEBUG Response: {response2.text[:200]}")

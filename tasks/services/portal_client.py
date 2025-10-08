"""Portal Backend V2 API client for employee profile and skills data."""

import logging
import os
from typing import Any

import jwt
import requests

logger = logging.getLogger(__name__)


class PortalClient:
    """Client for accessing Portal Backend V2 employee API."""

    def __init__(self):
        """Initialize the Portal API client."""
        self.portal_secret = os.getenv("PORTAL_SECRET")
        self.portal_url = os.getenv("PORTAL_URL", "https://portal.8thlight.com")
        self.portal_email = os.getenv(
            "PORTAL_EMAIL", "bot@8thlight.com"
        )  # Email for JWT auth

        if not self.portal_secret:
            raise ValueError("PORTAL_SECRET environment variable is required")

        # Generate JWT token for authentication
        self.token = self._generate_token()

    def _generate_token(self) -> str:
        """Generate JWT token signed with PORTAL_SECRET."""
        token = jwt.encode(
            {"email": self.portal_email}, self.portal_secret, algorithm="HS256"
        )
        return token

    def _make_request(
        self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Make authenticated request to Portal API.

        Args:
            endpoint: API endpoint (e.g., "/employees")
            method: HTTP method (GET, POST, PUT, etc.)
            data: Optional request body data

        Returns:
            Response JSON data

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.portal_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}"}

        logger.debug(f"Making {method} request to {url}")

        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "PUT":
            headers["Content-Type"] = "application/json"
            response = requests.put(url, headers=headers, json=data, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()

    def get_employees(self) -> list[dict[str, Any]]:
        """
        Get all current employees with profiles, skills, and allocations.

        Returns:
            List of employee objects with complete profile and skills data
        """
        logger.info("Fetching all employees from Portal API")
        employees = self._make_request("/employees")

        if not isinstance(employees, list):
            logger.error(f"Expected list of employees, got {type(employees)}")
            return []

        logger.info(f"Fetched {len(employees)} employees from Portal")
        return employees

    def get_employee(self, metric_id: str) -> dict[str, Any]:
        """
        Get detailed information for a specific employee.

        Args:
            metric_id: Employee's Metric.ai ID

        Returns:
            Employee object with complete profile, skills, allocations, and blog posts
        """
        logger.info(f"Fetching employee {metric_id} from Portal API")
        employee = self._make_request(f"/employees/{metric_id}")
        return employee

    def update_employee_profile(
        self, metric_id: str, profile_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update an employee's profile information including skills.

        Args:
            metric_id: Employee's Metric.ai ID
            profile_data: Profile data to update (must include complete skills array)

        Returns:
            Updated employee object

        Note:
            Requires authorization - must be the employee themselves OR an admin
        """
        logger.info(f"Updating profile for employee {metric_id}")
        return self._make_request(
            f"/employees/{metric_id}/profile", method="PUT", data={"profile": profile_data}
        )

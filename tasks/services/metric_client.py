"""Metric.ai GraphQL API client for data synchronization."""

import logging
import os
from typing import Any

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

logger = logging.getLogger(__name__)


class MetricClient:
    """Client for interacting with Metric.ai GraphQL API."""

    GRAPHQL_ENDPOINT = "https://api.psa.metric.ai/api/"

    def __init__(self, api_key: str | None = None):
        """
        Initialize the Metric.ai client.

        Args:
            api_key: Metric.ai API key (falls back to METRIC_API_KEY env var)

        Raises:
            ValueError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("METRIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing Metric API key (provide METRIC_API_KEY in environment)"
            )

        transport = RequestsHTTPTransport(
            url=self.GRAPHQL_ENDPOINT,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=False)

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            Query result dictionary

        Raises:
            Exception: If query execution fails
        """
        try:
            result = self.client.execute(gql(query), variable_values=variables or {})
            return result
        except Exception as e:
            logger.error(f"GraphQL query failed: {e}")
            raise

    def get_employees(self) -> list[dict[str, Any]]:
        """
        Fetch all employees from Metric.ai.

        Returns:
            List of employee dictionaries with id, name, email, groups, etc.
        """
        query = """
            query {
              organization {
                employees {
                  id
                  name
                  email
                  title
                  startedWorking
                  endedWorking
                  groups {
                    name
                    groupType
                  }
                }
              }
            }
        """
        result = self.execute(query)
        return result.get("organization", {}).get("employees", [])

    def get_clients(self) -> list[dict[str, Any]]:
        """
        Fetch all clients from Metric.ai.

        Returns:
            List of client dictionaries with id and name
        """
        query = """
            query {
              organization {
                groups(groupType: CLIENT) {
                  id
                  name
                }
              }
            }
        """
        result = self.execute(query)
        return result.get("organization", {}).get("groups", [])

    def get_projects(self) -> list[dict[str, Any]]:
        """
        Fetch all projects from Metric.ai.

        Returns:
            List of project dictionaries with id, name, type, status, dates, groups
        """
        query = """
            query {
              organization {
                projects {
                  id
                  name
                  projectType
                  projectStatus
                  endDate
                  startDate
                  groups {
                    id
                    groupType
                    name
                  }
                }
              }
            }
        """
        result = self.execute(query)
        return result.get("organization", {}).get("projects", [])

    def get_allocations(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """
        Fetch allocations for a date range from Metric.ai.

        Note: Metric.ai only allows querying one year at a time.

        Args:
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)

        Returns:
            List of allocation dictionaries
        """
        query = """
            query($startDate: Date, $endDate: Date) {
              organization {
                allocations(startDate: $startDate, endDate: $endDate) {
                  id
                  startDate
                  endDate
                  project {
                    id
                    name
                  }
                  employee {
                    id
                    name
                  }
                }
              }
            }
        """
        variables = {"startDate": start_date, "endDate": end_date}
        result = self.execute(query, variables)
        return result.get("organization", {}).get("allocations", [])

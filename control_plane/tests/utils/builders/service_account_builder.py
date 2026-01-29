"""Builder for creating service account request payloads in tests.

Provides fluent API and pre-configured scenarios for common integrations.
"""

from typing import Any


class ServiceAccountBuilder:
    """Fluent builder for service account request payloads.

    Examples:
        >>> builder = ServiceAccountBuilder()
        >>> payload = builder.for_hubspot().build()
        >>> payload = builder.named("Custom").with_scopes("agents:read").build()
    """

    def __init__(self):
        self._name = "Test Service Account"
        self._description: str | None = None
        self._scopes = "agents:read"
        self._rate_limit: int | None = None
        self._allowed_agents: list[str] | None = None
        self._is_active: bool | None = None

    def named(self, name: str) -> "ServiceAccountBuilder":
        """Set the service account name."""
        self._name = name
        return self

    def with_description(self, description: str) -> "ServiceAccountBuilder":
        """Set the description."""
        self._description = description
        return self

    def with_scopes(self, scopes: str) -> "ServiceAccountBuilder":
        """Set the scopes (comma-separated string)."""
        self._scopes = scopes
        return self

    def with_rate_limit(self, limit: int) -> "ServiceAccountBuilder":
        """Set the rate limit."""
        self._rate_limit = limit
        return self

    def with_allowed_agents(self, agents: list[str]) -> "ServiceAccountBuilder":
        """Set the allowed agents list."""
        self._allowed_agents = agents
        return self

    def with_is_active(self, is_active: bool) -> "ServiceAccountBuilder":
        """Set the is_active status (for update operations)."""
        self._is_active = is_active
        return self

    # Pre-configured scenarios

    def for_hubspot(self) -> "ServiceAccountBuilder":
        """Pre-configured for HubSpot CRM integration."""
        self._name = "HubSpot Production"
        self._description = "Integration with HubSpot CRM"
        self._scopes = "agents:read,agents:invoke"
        self._rate_limit = 500
        return self

    def for_salesforce(self) -> "ServiceAccountBuilder":
        """Pre-configured for Salesforce CRM integration."""
        self._name = "Salesforce Connector"
        self._description = "CRM data sync"
        self._scopes = "agents:read"
        self._rate_limit = 1000
        return self

    def read_only(self) -> "ServiceAccountBuilder":
        """Configure for read-only access."""
        self._scopes = "agents:read"
        return self

    def invoke_only(self) -> "ServiceAccountBuilder":
        """Configure for invoke-only access."""
        self._scopes = "agents:invoke"
        return self

    def full_access(self) -> "ServiceAccountBuilder":
        """Configure for full access (read + invoke)."""
        self._scopes = "agents:read,agents:invoke"
        return self

    def limited_to_agents(self, agents: list[str]) -> "ServiceAccountBuilder":
        """Limit access to specific agents."""
        self._allowed_agents = agents
        return self

    def no_agent_access(self) -> "ServiceAccountBuilder":
        """Configure with empty agents array (no access)."""
        self._allowed_agents = []
        return self

    def build(self) -> dict[str, Any]:
        """Build the service account request payload."""
        payload: dict[str, Any] = {
            "name": self._name,
            "scopes": self._scopes,
        }

        if self._description is not None:
            payload["description"] = self._description

        if self._rate_limit is not None:
            payload["rate_limit"] = self._rate_limit

        if self._allowed_agents is not None:
            payload["allowed_agents"] = self._allowed_agents

        if self._is_active is not None:
            payload["is_active"] = self._is_active

        return payload

    # Static factory methods for common use cases

    @staticmethod
    def default() -> "ServiceAccountBuilder":
        """Create builder with default test values."""
        return ServiceAccountBuilder()

    @staticmethod
    def minimal() -> "ServiceAccountBuilder":
        """Create builder with minimal required fields."""
        return ServiceAccountBuilder().named("Test Account").with_scopes("agents:read")

    @staticmethod
    def hubspot() -> "ServiceAccountBuilder":
        """Create HubSpot integration builder."""
        return ServiceAccountBuilder().for_hubspot()

    @staticmethod
    def salesforce() -> "ServiceAccountBuilder":
        """Create Salesforce integration builder."""
        return ServiceAccountBuilder().for_salesforce()

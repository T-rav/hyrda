"""Tests for agent management API endpoints.

TODO: These tests need to be integrated with existing test fixtures in conftest.py
Missing fixtures:
- db_session (or use API calls instead of direct DB access)
- service_authenticated_client (for service-to-service auth)
- admin_authenticated_client (or reuse existing authenticated_client)

These tests are reference implementations showing what should be tested.
Adapt them to match the existing test patterns in this codebase.
"""

# NOTE: Tests currently disabled - see TODO above
# Run with: pytest tests/test_agents_api.py --tb=short

# Reference test structure (needs fixture adaptation):
# - TestListAgents: List agents with/without deleted agents
# - TestRegisterAgent: Register new agents, update existing, preserve customized aliases
# - TestUpdateAliases: Admin updates, validation, permission checks
# - TestAliasConflicts: Detect alias conflicts with other agents
# - TestToggleAgent: Enable/disable agents, toggle Slack visibility
# - TestDeleteAgent: Soft delete, cannot delete system agents

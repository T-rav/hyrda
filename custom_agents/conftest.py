"""Pytest configuration for custom_agents tests."""


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires external services)"
    )

"""Profile Agent - Company research and profiling.

This is the main entry point for the external agent loader.
The Agent class is imported and exposed for dynamic loading.
"""

from profile_researcher import ProfileResearcher

# Export Agent class for external loader
Agent = ProfileResearcher

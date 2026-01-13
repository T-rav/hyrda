"""MEDDIC Coach Agent - Sales qualification coaching.

This is the main entry point for the external agent loader.
The Agent class is imported and exposed for dynamic loading.
"""

from .meddpicc_coach import meddpicc_coach

# Export Agent (graph instance) for external loader
Agent = meddpicc_coach

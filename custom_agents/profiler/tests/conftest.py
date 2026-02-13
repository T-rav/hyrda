"""Pytest configuration for profiler tests.

Ensures the profiler package is importable during test collection.
"""

import sys
from pathlib import Path

# Add custom_agents directory to path so 'profiler' is importable
# This mirrors the PYTHONPATH=custom_agents setup used in the Makefile
custom_agents_root = Path(__file__).parent.parent.parent
if str(custom_agents_root) not in sys.path:
    sys.path.insert(0, str(custom_agents_root))

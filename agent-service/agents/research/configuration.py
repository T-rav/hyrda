"""Configuration for deep research agent."""

import os

# Cache directory for storing downloaded data
RESEARCH_CACHE_DIR = os.getenv(
    "RESEARCH_CACHE_DIR",
    "/tmp/research_cache",  # Default to /tmp, override in production
)

# Research depth settings
RESEARCH_DEPTH_SETTINGS = {
    "quick": {
        "max_tasks": 3,
        "max_tool_calls": 10,
        "max_iterations": 2,
        "recursion_limit": 50,
    },
    "standard": {
        "max_tasks": 5,
        "max_tool_calls": 20,
        "max_iterations": 3,
        "recursion_limit": 100,
    },
    "deep": {
        "max_tasks": 10,
        "max_tool_calls": 50,
        "max_iterations": 5,
        "recursion_limit": 150,
    },
    "exhaustive": {
        "max_tasks": 20,
        "max_tool_calls": 100,
        "max_iterations": 10,
        "recursion_limit": 200,
    },
}

# Quality control settings
MAX_REVISIONS = 3
MIN_REPORT_LENGTH = 1000  # characters
MIN_FINDINGS_COUNT = 3

# File naming conventions for cache
FILE_NAMING_PATTERNS = {
    "sec_filing": "{company}_{form_type}_{year}_{quarter}.txt",
    "web_page": "{domain}_{slug}_{timestamp}.html",
    "pdf": "{source}_{title}_{timestamp}.pdf",
    "json_data": "{source}_{query_hash}_{timestamp}.json",
}

# LLM settings
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
FAST_MODEL = os.getenv("LLM_FAST_MODEL", "gpt-4o-mini")

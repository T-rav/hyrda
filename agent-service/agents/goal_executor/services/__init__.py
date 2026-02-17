"""Services for goal executor.

Two memory systems:

1. **GoalMemory** (MinIO): Structured storage
   - Session activity logs (thread_id scoped)
   - Goal-wide sets (all companies searched, etc.)
   - Full research artifacts and run history

2. **VectorMemory** (Qdrant): Semantic search
   - Session summaries (LLM-compacted)
   - Temporal decay for recency
   - Natural language queries across past runs
"""

from .memory import GoalMemory, get_goal_memory
from .vector_memory import VectorMemory, get_vector_memory

__all__ = [
    "GoalMemory",
    "get_goal_memory",
    "VectorMemory",
    "get_vector_memory",
]

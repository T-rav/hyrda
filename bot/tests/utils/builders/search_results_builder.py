"""
SearchResultsBuilder for test utilities
"""

from typing import Any


class SearchResultsBuilder:
    """Builder for creating lists of search results"""

    def __init__(self):
        self._results = []

    def add_result(
        self,
        content: str,
        similarity: float = 0.85,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a search result"""
        result = {
            "id": f"result-{len(self._results) + 1}",
            "content": content,
            "similarity": similarity,
            "metadata": metadata or {},
        }
        self._results.append(result)
        return self

    def add_results_with_similarity_range(
        self,
        count: int,
        content_prefix: str = "Content",
        similarity_range: tuple[float, float] = (0.7, 0.9),
    ):
        """Add multiple results with similarity in range"""
        sim_min, sim_max = similarity_range
        sim_step = (sim_max - sim_min) / (count - 1) if count > 1 else 0

        for i in range(count):
            similarity = sim_max - (i * sim_step)
            self.add_result(
                content=f"{content_prefix} {i + 1}",
                similarity=similarity,
            )
        return self

    def build(self) -> list[dict[str, Any]]:
        """Build the search results list"""
        return self._results.copy()

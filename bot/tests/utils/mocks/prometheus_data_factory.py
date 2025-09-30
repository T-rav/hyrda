"""
PrometheusDataFactory for test utilities
"""

from typing import Any


class PrometheusDataFactory:
    """Factory for creating Prometheus metric data"""

    @staticmethod
    def create_counter_data(
        name: str = "test_counter", value: float = 10.0
    ) -> dict[str, Any]:
        """Create Prometheus counter data"""
        return {
            "name": name,
            "type": "counter",
            "help": f"Test counter {name}",
            "samples": [{"value": value, "labels": {}}],
        }

    @staticmethod
    def create_gauge_data(
        name: str = "test_gauge", value: float = 5.0
    ) -> dict[str, Any]:
        """Create Prometheus gauge data"""
        return {
            "name": name,
            "type": "gauge",
            "help": f"Test gauge {name}",
            "samples": [{"value": value, "labels": {}}],
        }

    @staticmethod
    def create_histogram_data(
        name: str = "test_histogram",
        buckets: list[tuple[float, int]] | None = None,
    ) -> dict[str, Any]:
        """Create Prometheus histogram data"""
        if buckets is None:
            buckets = [(0.1, 5), (0.5, 10), (1.0, 15)]

        samples = [
            {"value": count, "labels": {"le": str(bucket)}} for bucket, count in buckets
        ]
        samples.append({"value": sum(c for _, c in buckets), "labels": {"le": "+Inf"}})

        return {
            "name": name,
            "type": "histogram",
            "help": f"Test histogram {name}",
            "samples": samples,
        }

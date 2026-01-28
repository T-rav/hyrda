#!/usr/bin/env python3
"""Check Langfuse traces to verify distributed tracing is working."""

import os
import sys
from datetime import datetime, timedelta

# Add bot and shared to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from services.langfuse_service import get_langfuse_service


def main():
    """Check recent traces in Langfuse."""
    langfuse_service = get_langfuse_service()
    if not langfuse_service or not langfuse_service.client:
        print("❌ Langfuse service not initialized")
        return

    print("✅ Langfuse service initialized")
    print(f"   Environment: {langfuse_service.environment}")
    print()

    # Fetch recent traces (last 24 hours)
    print("📊 Fetching recent traces...")
    try:
        # Use the Langfuse SDK to fetch traces
        client = langfuse_service.client

        # Get traces with pagination
        page = 1
        traces = []
        while True:
            response = client.fetch_traces(page=page, limit=50)
            if not response.data:
                break
            traces.extend(response.data)
            if not response.meta.total_pages or page >= response.meta.total_pages:
                break
            page += 1

        print(f"   Found {len(traces)} total traces")
        print()

        # Filter to recent traces (last hour)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_traces = [
            t for t in traces
            if t.timestamp and t.timestamp.replace(tzinfo=None) > one_hour_ago
        ]

        print(f"🔍 Recent traces (last hour): {len(recent_traces)}")
        print()

        if not recent_traces:
            print("   No traces in the last hour. Try running 'profile <company>' in Slack.")
            return

        # Analyze each recent trace
        for trace in recent_traces[:10]:  # Show up to 10 most recent
            print(f"📍 Trace: {trace.name}")
            print(f"   ID: {trace.id}")
            print(f"   Timestamp: {trace.timestamp}")

            # Fetch observations for this trace
            observations = client.fetch_observations(trace_id=trace.id)
            if observations and observations.data:
                print(f"   Observations: {len(observations.data)}")

                # Count by type
                spans = [o for o in observations.data if o.type == "SPAN"]
                generations = [o for o in observations.data if o.type == "GENERATION"]
                events = [o for o in observations.data if o.type == "EVENT"]

                print(f"      - Spans: {len(spans)}")
                print(f"      - Generations: {len(generations)}")
                print(f"      - Events: {len(events)}")

                # Show span hierarchy
                if spans:
                    print("   Span hierarchy:")
                    # Find root spans (no parent)
                    root_spans = [s for s in spans if not s.parent_observation_id]

                    def print_span_tree(span, indent=0):
                        prefix = "   " + "  " * indent + "└─ "
                        print(f"{prefix}{span.name} ({span.id[:8]}...)")
                        # Find children
                        children = [s for s in spans if s.parent_observation_id == span.id]
                        for child in children:
                            print_span_tree(child, indent + 1)

                    for root in root_spans:
                        print_span_tree(root)

                # Check for distributed tracing (multiple services)
                services = set()
                for obs in observations.data:
                    if obs.metadata and isinstance(obs.metadata, dict):
                        service = obs.metadata.get("service") or obs.metadata.get("entry_point")
                        if service:
                            services.add(service)

                if services:
                    print(f"   Services involved: {', '.join(services)}")
                    if len(services) > 1:
                        print("      ✅ Multi-service trace detected!")
                    else:
                        print("      ⚠️  Single service only")
                else:
                    print("      ⚠️  No service metadata found")

            print()

    except Exception as e:
        print(f"❌ Error fetching traces: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

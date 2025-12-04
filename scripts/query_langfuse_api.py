"""
Query Langfuse API directly via HTTP to find Baker College trace
"""

import os
import sys
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from config.settings import Settings


def main():
    # Set minimal env vars for Settings to load
    os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-dummy")
    os.environ.setdefault("SLACK_APP_TOKEN", "xapp-dummy")
    os.environ.setdefault("LLM_PROVIDER", "openai")
    os.environ.setdefault("LLM_API_KEY", "dummy")

    # Load settings
    settings = Settings()

    if not settings.langfuse.enabled:
        print("Langfuse is not enabled in settings")
        return

    # Get credentials
    public_key = settings.langfuse.public_key
    secret_key = settings.langfuse.secret_key.get_secret_value()
    host = settings.langfuse.host.rstrip("/")

    print(f"Querying Langfuse API at: {host}")
    print("=" * 80)

    # Query traces via API
    # API docs: https://api.reference.langfuse.com/
    api_url = f"{host}/api/public/traces"

    auth = HTTPBasicAuth(public_key, secret_key)

    # Get traces from last 48 hours
    params = {
        "page": 1,
        "limit": 50,
    }

    try:
        response = requests.get(api_url, auth=auth, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        traces = data.get("data", [])

        print(f"Found {len(traces)} recent traces")
        print("=" * 80)
        print()

        # Search for Baker College or Munich Re
        baker_traces = []
        munich_traces = []

        for trace in traces:
            trace_id = trace.get("id", "N/A")
            trace_name = trace.get("name", "")
            trace_input = trace.get("input", {})
            trace_output = trace.get("output", {})
            trace_metadata = trace.get("metadata", {})
            trace_ts = trace.get("timestamp", "N/A")

            # Convert to strings for searching
            trace_str = json.dumps(
                {
                    "name": trace_name,
                    "input": trace_input,
                    "output": trace_output,
                    "metadata": trace_metadata,
                }
            ).lower()

            if "baker" in trace_str:
                baker_traces.append(
                    {
                        "id": trace_id,
                        "name": trace_name,
                        "timestamp": trace_ts,
                        "input": trace_input,
                        "output": trace_output,
                        "metadata": trace_metadata,
                    }
                )

            if "munich" in trace_str or "münchener" in trace_str:
                munich_traces.append(
                    {
                        "id": trace_id,
                        "name": trace_name,
                        "timestamp": trace_ts,
                        "input": trace_input,
                        "metadata": trace_metadata,
                    }
                )

        # Report findings
        if baker_traces:
            print(f"🎯 FOUND {len(baker_traces)} BAKER COLLEGE TRACE(S)!")
            print("=" * 80)
            for i, trace in enumerate(baker_traces, 1):
                print(f"\n--- Baker Trace {i} ---")
                print(f"Trace ID: {trace['id']}")
                print(f"Trace Name: {trace['name']}")
                print(f"Timestamp: {trace['timestamp']}")
                print("\nInput:")
                print(json.dumps(trace["input"], indent=2)[:500])
                print("\nMetadata:")
                print(json.dumps(trace["metadata"], indent=2)[:500])
                print("\nOutput (first 500 chars):")
                output_str = json.dumps(trace["output"], indent=2)[:500]
                print(output_str)
                if "munich" in output_str.lower():
                    print(
                        "\n⚠️  WARNING: This Baker College trace mentions Munich Re in output!"
                    )
                print("-" * 80)

        if munich_traces:
            print(f"\n🔍 Found {len(munich_traces)} Munich Re trace(s)")
            print("=" * 80)
            for i, trace in enumerate(munich_traces, 1):
                print(f"\n--- Munich Trace {i} ---")
                print(f"Trace ID: {trace['id']}")
                print(f"Trace Name: {trace['name']}")
                print(f"Timestamp: {trace['timestamp']}")

                # Check if input mentions Baker
                input_str = json.dumps(trace["input"])
                if "baker" in input_str.lower():
                    print("\n⚠️⚠️⚠️  CRITICAL: Munich Re trace has 'Baker' in input!")
                    print(f"Input: {input_str[:500]}")
                else:
                    print(f"Input (first 200 chars): {input_str[:200]}")
                print("-" * 80)

        if not baker_traces and not munich_traces:
            print("❌ No Baker College or Munich Re traces found in recent traces")
            print("\nShowing first 3 traces for reference:")
            for trace in traces[:3]:
                print(f"\nTrace: {trace.get('name', 'N/A')}")
                print(f"ID: {trace.get('id', 'N/A')}")
                print(f"Timestamp: {trace.get('timestamp', 'N/A')}")
                print(f"Input keys: {list(trace.get('input', {}).keys())}")

        # Now get observations for the Baker College trace if found
        if baker_traces:
            print("\n" + "=" * 80)
            print("QUERYING OBSERVATIONS FOR BAKER COLLEGE TRACE...")
            print("=" * 80)

            for trace in baker_traces:
                trace_id = trace["id"]
                print(f"\nFetching observations for trace: {trace_id}")

                obs_url = f"{host}/api/public/observations"
                obs_params = {"page": 1, "limit": 100, "traceId": trace_id}

                obs_response = requests.get(
                    obs_url, auth=auth, params=obs_params, timeout=30
                )
                obs_response.raise_for_status()

                obs_data = obs_response.json()
                observations = obs_data.get("data", [])

                print(f"Found {len(observations)} observations")

                # Look for where Munich Re appears
                for obs in observations:
                    obs_name = obs.get("name", "")
                    obs_type = obs.get("type", "")
                    obs_input = obs.get("input", {})
                    obs_output = obs.get("output", {})

                    obs_str = json.dumps(
                        {"name": obs_name, "input": obs_input, "output": obs_output}
                    ).lower()

                    if "munich" in obs_str:
                        print("\n🚨 FOUND MUNICH RE IN OBSERVATION:")
                        print(f"  Observation Name: {obs_name}")
                        print(f"  Observation Type: {obs_type}")
                        print(
                            f"  Input (first 300 chars): {json.dumps(obs_input)[:300]}"
                        )
                        print(
                            f"  Output (first 300 chars): {json.dumps(obs_output)[:300]}"
                        )
                        print()

    except requests.exceptions.RequestException as e:
        print(f"Error querying Langfuse API: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text[:500]}")


if __name__ == "__main__":
    main()

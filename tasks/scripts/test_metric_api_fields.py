#!/usr/bin/env python3
"""Test script to verify what fields Metric.ai API actually returns for employees."""

import json
import sys
from pathlib import Path

# Load .env file
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.metric_client import MetricClient


def main():
    """Fetch and print employee fields from Metric.ai API."""
    print("🔍 Fetching employee data from Metric.ai API...\n")

    try:
        client = MetricClient()
        employees = client.get_employees()

        if not employees:
            print("❌ No employees returned from API")
            return

        print(f"✅ Found {len(employees)} employees\n")

        # Filter to active employees with groups
        active_with_groups = [
            e for e in employees
            if not e.get("endedWorking") and len(e.get("groups", [])) > 2
        ]

        print(f"Active employees with groups: {len(active_with_groups)}\n")
        print("=" * 80)
        print("EMPLOYEE FIELDS FOR 5 ACTIVE EMPLOYEES")
        print("=" * 80)

        # Print all fields for first 5 active employees with groups
        for i, employee in enumerate(active_with_groups[:5], 1):
            print(f"\n{'=' * 80}")
            print(f"EMPLOYEE #{i}: {employee.get('name', 'Unknown')}")
            print(f"{'=' * 80}")
            print(json.dumps(employee, indent=2, default=str))

        # Print available field names
        print("\n" + "=" * 80)
        print("AVAILABLE FIELD NAMES")
        print("=" * 80)
        if employees:
            all_fields = set()
            for emp in employees:
                all_fields.update(emp.keys())
            print(f"Fields: {sorted(all_fields)}")

            # Check specifically for title-related fields
            title_fields = [
                f for f in all_fields if "title" in f.lower() or "role" in f.lower()
            ]
            print(f"\nTitle/Role fields: {title_fields if title_fields else 'NONE FOUND'}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

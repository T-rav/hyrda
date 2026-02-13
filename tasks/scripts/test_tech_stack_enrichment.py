#!/usr/bin/env python3
"""Test script to verify tech stack enrichment from HubSpot to Metric.

This script tests:
1. HubSpot deal lookup by name and client
2. Tech stack extraction from stored deals
3. Metric project -> HubSpot tech stack mapping

Run with: PYTHONPATH=tasks python tasks/scripts/test_tech_stack_enrichment.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path before importing local modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

from services.hubspot_deal_tracking_service import (  # noqa: E402
    HubSpotDealTrackingService,
)
from services.metric_client import MetricClient  # noqa: E402

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


def test_hubspot_deal_lookup():
    """Test looking up deals and extracting tech stack."""
    print("=" * 60)
    print("TESTING HUBSPOT DEAL TECH STACK LOOKUP")
    print("=" * 60)

    service = HubSpotDealTrackingService()

    # Get all synced deals
    print("\n📋 Fetching all synced deals...")
    deals = service.get_all_synced_deals()
    print(f"Found {len(deals)} synced deals\n")

    if not deals:
        print("❌ No deals found in database. Run HubSpot sync first.")
        return False

    # Show first 5 deals
    print("First 5 deals:")
    for deal in deals[:5]:
        print(f"  - {deal['deal_name']} (ID: {deal['hubspot_deal_id']})")

    # Test tech stack extraction for first deal with content
    print("\n🔍 Testing tech stack extraction...")
    for deal in deals[:5]:
        deal_id = deal["hubspot_deal_id"]
        tech_stack = service.get_tech_stack_for_deal(deal_id)
        if tech_stack:
            print(f"  ✅ {deal['deal_name']}: {tech_stack}")
        else:
            print(f"  ⚠️  {deal['deal_name']}: No tech stack found")

    # Test client name lookup
    print("\n🔍 Testing tech stack by client name...")
    # Extract some client names from deal names
    test_clients = []
    for deal in deals[:5]:
        # Deal names often start with client name
        deal_name = deal.get("deal_name", "")
        if " - " in deal_name:
            client = deal_name.split(" - ")[0]
            test_clients.append(client)

    for client in test_clients[:3]:
        tech_stack = service.get_tech_stack_by_client_name(client)
        if tech_stack:
            print(f"  ✅ Client '{client}': {tech_stack}")
        else:
            print(f"  ⚠️  Client '{client}': No tech stack found")

    return True


def test_metric_project_mapping():
    """Test Metric project to tech stack mapping."""
    print("\n" + "=" * 60)
    print("TESTING METRIC PROJECT -> TECH STACK MAPPING")
    print("=" * 60)

    try:
        metric_client = MetricClient()
    except ValueError as e:
        print(f"❌ Cannot connect to Metric: {e}")
        return False

    hubspot_service = HubSpotDealTrackingService()

    # Get projects
    print("\n📋 Fetching Metric projects...")
    try:
        projects = metric_client.get_projects()
    except Exception as e:
        print(f"❌ Failed to fetch projects: {e}")
        return False

    print(f"Found {len(projects)} projects")

    # Filter to billable projects with clients
    billable_projects = [
        p
        for p in projects
        if p.get("projectType") == "BILLABLE"
        and any(g.get("groupType") == "CLIENT" for g in p.get("groups", []))
    ]
    print(f"Billable projects with clients: {len(billable_projects)}")

    # Test tech stack mapping for first 10 projects
    print("\n🔍 Testing tech stack mapping for projects...")
    matches = 0
    for project in billable_projects[:10]:
        project_name = project.get("name", "")
        client = next(
            (
                g["name"]
                for g in project.get("groups", [])
                if g["groupType"] == "CLIENT"
            ),
            None,
        )

        tech_stack = []

        # Try client name lookup
        if client:
            tech_stack = hubspot_service.get_tech_stack_by_client_name(client)

        # Try project name lookup if no match
        if not tech_stack:
            tech_stack = hubspot_service.get_tech_stack_by_client_name(project_name)

        if tech_stack:
            print(f"  ✅ {project_name}")
            print(f"      Client: {client}")
            print(
                f"      Tech Stack: {', '.join(tech_stack[:5])}{'...' if len(tech_stack) > 5 else ''}"
            )
            matches += 1
        else:
            print(f"  ⚠️  {project_name} (Client: {client}) - No tech stack match")

    print(
        f"\n📊 Summary: {matches}/{min(10, len(billable_projects))} projects matched with tech stack"
    )
    return matches > 0


def test_metric_employee_tech_stack():
    """Test tech stack aggregation for employees."""
    print("\n" + "=" * 60)
    print("TESTING EMPLOYEE TECH STACK AGGREGATION")
    print("=" * 60)

    try:
        metric_client = MetricClient()
    except ValueError as e:
        print(f"❌ Cannot connect to Metric: {e}")
        return False

    hubspot_service = HubSpotDealTrackingService()

    # Get employees
    print("\n📋 Fetching Metric employees...")
    employees = metric_client.get_employees()
    active_employees = [e for e in employees if not e.get("endedWorking")]
    print(f"Found {len(active_employees)} active employees")

    # Get allocations for project history
    print("\n📋 Fetching allocations...")
    from datetime import datetime

    current_year = datetime.now().year
    all_allocations = []
    for year in range(2022, current_year + 1):
        try:
            allocs = metric_client.get_allocations(f"{year}-01-01", f"{year + 1}-01-01")
            all_allocations.extend(allocs)
        except Exception:
            pass
    print(f"Found {len(all_allocations)} allocations")

    # Build employee -> project mapping
    emp_projects = {}
    for alloc in all_allocations:
        emp = alloc.get("employee", {})
        proj = alloc.get("project", {})
        if emp.get("id") and proj.get("name"):
            if emp["id"] not in emp_projects:
                emp_projects[emp["id"]] = set()
            emp_projects[emp["id"]].add(proj["name"])

    # Get projects for client mapping
    projects = metric_client.get_projects()
    project_clients = {}
    for p in projects:
        client = next(
            (g["name"] for g in p.get("groups", []) if g["groupType"] == "CLIENT"),
            None,
        )
        if client:
            project_clients[p["name"]] = client

    # Test tech stack for first 5 active employees with projects
    print("\n🔍 Testing tech stack for employees...")
    tested = 0
    for emp in active_employees:
        emp_id = emp.get("id")
        if emp_id not in emp_projects:
            continue

        tested += 1
        if tested > 5:
            break

        emp_name = emp.get("name", "Unknown")
        projects_list = list(emp_projects[emp_id])

        # Collect tech stacks from all projects
        all_tech = set()
        for proj_name in projects_list:
            client = project_clients.get(proj_name)
            if client:
                tech = hubspot_service.get_tech_stack_by_client_name(client)
                all_tech.update(tech)
            # Also try project name
            tech = hubspot_service.get_tech_stack_by_client_name(proj_name)
            all_tech.update(tech)

        print(f"\n  👤 {emp_name}")
        print(
            f"      Projects: {', '.join(projects_list[:3])}{'...' if len(projects_list) > 3 else ''}"
        )
        if all_tech:
            print(
                f"      Tech Stack: {', '.join(sorted(all_tech)[:5])}{'...' if len(all_tech) > 5 else ''}"
            )
        else:
            print("      Tech Stack: None found")

    return True


if __name__ == "__main__":
    print("🧪 TECH STACK ENRICHMENT TEST SCRIPT")
    print("=" * 60)

    results = []

    # Test HubSpot lookup
    results.append(("HubSpot Deal Lookup", test_hubspot_deal_lookup()))

    # Test Metric project mapping
    results.append(("Metric Project Mapping", test_metric_project_mapping()))

    # Test employee tech stack
    results.append(("Employee Tech Stack", test_metric_employee_tech_stack()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")

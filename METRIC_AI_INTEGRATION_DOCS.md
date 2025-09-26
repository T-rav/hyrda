# Metric.ai Integration Documentation

## Overview

The Portal Backend V2 integrates with Metric.ai's GraphQL API to synchronize employee, client, project, allocation, invoice, and manager assignment data. This document provides comprehensive details for replicating this integration in Python.

## Architecture

The integration is built around a centralized GraphQL client with specific jobs for each data type:

- **Core Integration**: `lib/integration/metric.rb` - GraphQL client setup and authentication
- **Data Sync Jobs**: Background jobs that fetch and process data from Metric.ai
- **Rake Tasks**: `lib/tasks/sync.rake` - Orchestrates all sync operations

## Authentication

### Rails Implementation
```ruby
# lib/integration/metric.rb
HTTP_ADAPTER = GraphQL::Client::HTTP.new("https://api.psa.metric.ai/api/") do
  def headers(_)
    unless (api_key = PORTAL_ENV.metric_api_key)
      raise "Missing Metric API key (provide METRIC_API_KEY in environment)"
    end
    {"Authorization" => "Bearer #{api_key}"}
  end
end
```

### Python Equivalent
```python
import os
import requests
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

class MetricClient:
    def __init__(self):
        api_key = os.getenv('METRIC_API_KEY')
        if not api_key:
            raise ValueError("Missing Metric API key (provide METRIC_API_KEY in environment)")

        transport = RequestsHTTPTransport(
            url="https://api.psa.metric.ai/api/",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        self.client = Client(transport=transport)

    def execute(self, query, variables=None):
        return self.client.execute(query, variable_values=variables)
```

## API Endpoints and Data Models

### 1. Employees (`EmployeesJob`)

**GraphQL Query:**
```graphql
query {
  organization {
    employees {
      id
      name
      email
      startedWorking
      endedWorking
      groups {
        name
        groupType
      }
    }
  }
}
```

**Key Group Types:**
- `GROUP_TYPE_11`: Role/Position
- `GROUP_TYPE_17`: Bench status (name "True" = on bench)
- `DEPARTMENT`: Department assignment
- `GROUP_TYPE_23`: Practice assignment

**Python Implementation:**
```python
EMPLOYEES_QUERY = gql("""
    query {
      organization {
        employees {
          id
          name
          email
          startedWorking
          endedWorking
          groups {
            name
            groupType
          }
        }
      }
    }
""")

def sync_employees():
    result = metric_client.execute(EMPLOYEES_QUERY)

    for employee_data in result['organization']['employees']:
        employee_id = employee_data['id']

        # Extract role from groups
        role = next((g['name'] for g in employee_data['groups']
                    if g['groupType'] == 'GROUP_TYPE_11'), None)

        # Check if on bench
        on_bench = any(g['groupType'] == 'GROUP_TYPE_17' and g['name'] == 'True'
                      for g in employee_data['groups'])

        # Extract department
        department = next((g['name'] for g in employee_data['groups']
                          if g['groupType'] == 'DEPARTMENT'), None)

        # Extract practice
        practice = next((g['name'] for g in employee_data['groups']
                        if g['groupType'] == 'GROUP_TYPE_23'), None)

        # Process employee data...
```

### 2. Clients (`ClientsJob`)

**GraphQL Query:**
```graphql
query {
  organization {
    groups(groupType: CLIENT) {
      id
      name
    }
  }
}
```

**Python Implementation:**
```python
CLIENTS_QUERY = gql("""
    query {
      organization {
        groups(groupType: CLIENT) {
          id
          name
        }
      }
    }
""")

def sync_clients():
    result = metric_client.execute(CLIENTS_QUERY)

    for client_data in result['organization']['groups']:
        client_id = client_data['id']
        client_name = client_data['name']
        # Process client data...
```

### 3. Projects (`ProjectsJob`)

**GraphQL Query:**
```graphql
query {
  organization {
    projects {
      id
      name
      projectType
      projectStatus
      endDate
      startDate
      groups {
        id
        groupType
        name
      }
    }
  }
}
```

**Key Group Types:**
- `CLIENT`: Associated client
- `GROUP_TYPE_7`: Billing frequency
- `GROUP_TYPE_12`: Delivery owner

**Business Rules:**
- Only process `BILLABLE` projects
- Skip projects without groups or client association

**Python Implementation:**
```python
PROJECTS_QUERY = gql("""
    query {
      organization {
        projects {
          id
          name
          projectType
          projectStatus
          endDate
          startDate
          groups {
            id
            groupType
            name
          }
        }
      }
    }
""")

def sync_projects():
    result = metric_client.execute(PROJECTS_QUERY)

    for project_data in result['organization']['projects']:
        # Skip non-billable projects
        if project_data['projectType'] != 'BILLABLE':
            continue

        # Skip projects without groups
        if not project_data['groups']:
            continue

        # Extract client ID
        client_id = next((g['id'] for g in project_data['groups']
                         if g['groupType'] == 'CLIENT'), None)
        if not client_id:
            continue

        # Extract delivery owner
        delivery_owner = next((g['name'] for g in project_data['groups']
                              if g['groupType'] == 'GROUP_TYPE_12'), None)

        # Extract billing frequency
        billing_frequency = next((g['name'] for g in project_data['groups']
                                 if g['groupType'] == 'GROUP_TYPE_7'), 'Unknown')

        # Process project data...
```

### 4. Allocations (`AllocationsJob`)

**GraphQL Query:**
```graphql
query($startDate: Date, $endDate: Date) {
  organization {
    allocations(startDate: $startDate, endDate: $endDate) {
      id
      startDate
      endDate
      project {
        id
        name
      }
      employee {
        id
        name
      }
    }
  }
}
```

**Important Notes:**
- Metric.ai only allows querying one year at a time
- Query from 2020 (when 8th Light started using Metric) to current year
- Remove allocations not returned by Metric (they no longer exist)

**Python Implementation:**
```python
ALLOCATIONS_QUERY = gql("""
    query($startDate: Date, $endDate: Date) {
      organization {
        allocations(startDate: $startDate, endDate: $endDate) {
          id
          startDate
          endDate
          project {
            id
            name
          }
          employee {
            id
            name
          }
        }
      }
    }
""")

def sync_allocations():
    from datetime import datetime, date

    start_year = 2020
    current_year = datetime.now().year
    all_allocations = []

    # Query year by year
    for year in range(start_year, current_year + 1):
        variables = {
            "startDate": date(year, 1, 1).isoformat(),
            "endDate": date(year + 1, 1, 1).isoformat()
        }

        result = metric_client.execute(ALLOCATIONS_QUERY, variables)
        all_allocations.extend(result['organization']['allocations'])

    # Remove duplicates by ID
    unique_allocations = {alloc['id']: alloc for alloc in all_allocations}.values()

    # Process allocations...
    for allocation_data in unique_allocations:
        if not allocation_data.get('employee', {}).get('id'):
            continue
        if not allocation_data.get('project', {}).get('id'):
            continue
        # Process allocation data...
```

### 5. Invoices (`InvoicesJob`)

**GraphQL Query:**
```graphql
query {
  organization {
    invoices {
      id
      client {
        name
        id
      }
      project{
        id
      }
      dueDate
      invoiceStatus
      totalAmount
    }
  }
}
```

**Business Rules:**
- Only process invoices with due date from 2020 onwards
- Skip invoices without associated client or project

**Python Implementation:**
```python
INVOICES_QUERY = gql("""
    query {
      organization {
        invoices {
          id
          client {
            name
            id
          }
          project{
            id
          }
          dueDate
          invoiceStatus
          totalAmount
        }
      }
    }
""")

def sync_invoices():
    from datetime import datetime

    result = metric_client.execute(INVOICES_QUERY)

    for invoice_data in result['organization']['invoices']:
        # Skip invoices without client or project
        if not invoice_data.get('client', {}).get('id'):
            continue
        if not invoice_data.get('project', {}).get('id'):
            continue

        # Skip old invoices
        due_date = datetime.fromisoformat(invoice_data['dueDate'])
        if due_date.year < 2020:
            continue

        # Process invoice data...
```

### 6. Manager Assignments (`ManagerAssignmentsJob`)

**GraphQL Query:**
```graphql
query {
  organization {
    groupAssignments {
      employee {
        id
        name
      }
      active
      startDate
      endDate
      id
      group {
        id
        name
        groupType
      }
    }
  }
}
```

**Key Group Types:**
- `GROUP_TYPE_14`: Manager assignments
- `GROUP_TYPE_16`: Mentor assignments (also treated as managers)

**Business Rules:**
- Filter locally for manager group types (API doesn't support filtering)
- Use default start date "2021-01-01" if not provided
- Remove assignments that no longer exist in Metric

**Python Implementation:**
```python
MANAGER_ASSIGNMENTS_QUERY = gql("""
    query {
      organization {
        groupAssignments {
          employee {
            id
            name
          }
          active
          startDate
          endDate
          id
          group {
            id
            name
            groupType
          }
        }
      }
    }
""")

def sync_manager_assignments():
    result = metric_client.execute(MANAGER_ASSIGNMENTS_QUERY)

    manager_group_types = ["GROUP_TYPE_14", "GROUP_TYPE_16"]
    current_assignment_ids = []

    for assignment_data in result['organization']['groupAssignments']:
        # Filter for manager/mentor assignments
        if assignment_data['group']['groupType'] not in manager_group_types:
            continue

        current_assignment_ids.append(assignment_data['id'])

        # Skip if missing employee or manager
        if not assignment_data.get('employee', {}).get('id'):
            continue
        if not assignment_data['group']['name']:
            continue

        start_date = assignment_data['startDate'] or "2021-01-01"

        # Process manager assignment...

    # Remove assignments that no longer exist in Metric
    # (Implementation depends on your data storage)
```

## Data Synchronization Strategy

### Rails Implementation Pattern
1. **Lookup Tables**: Create in-memory hash maps for existing records to avoid N+1 queries
2. **Upsert Logic**: Check if record exists, create if new, update if changed
3. **Logging**: Comprehensive logging for skipped, created, and updated records
4. **Error Handling**: Graceful handling with Slack notifications

### Python Implementation Pattern
```python
class DataSyncer:
    def __init__(self):
        self.metric_client = MetricClient()
        self.logger = logging.getLogger(__name__)

    def create_lookup_table(self, records, key_field):
        """Create lookup table to avoid N+1 queries"""
        return {getattr(record, key_field): record for record in records}

    def upsert_record(self, model_class, lookup_key, data):
        """Generic upsert logic"""
        existing = self.lookup_tables.get(model_class, {}).get(lookup_key)

        if existing:
            # Update existing record
            if self.has_changes(existing, data):
                self.update_record(existing, data)
                self.logger.info(f"Updated {model_class.__name__} with ID {lookup_key}")
            else:
                self.logger.debug(f"Skipped {model_class.__name__} with ID {lookup_key} - no changes")
        else:
            # Create new record
            new_record = self.create_record(model_class, data)
            self.logger.info(f"Created new {model_class.__name__} with ID {lookup_key}")
```

## Error Handling and Monitoring

### Authentication Errors
- Check for missing or invalid `METRIC_API_KEY`
- Handle 401/403 responses gracefully

### Rate Limiting
- Metric.ai may have rate limits
- Implement exponential backoff for retry logic

### Data Integrity
- Validate required fields before processing
- Skip malformed records with appropriate logging
- Maintain referential integrity (employees before projects, clients before projects, etc.)

### Logging Strategy
```python
import logging

logger = logging.getLogger('metric_sync')

# Log levels used in Rails implementation:
# - INFO: Record created/updated, important skips
# - WARN: Data issues, missing relationships
# - DEBUG: No-change skips
# - ERROR: Actual errors that need attention
```

## Environment Configuration

Required environment variables:
- `METRIC_API_KEY`: Bearer token for Metric.ai API authentication

Optional configuration:
- Sync scheduling (Rails uses daily cron at midnight UTC)
- Error notification endpoints (Rails sends to Slack)

## Dependencies

### Python Packages
```bash
pip install gql[requests] requests python-dateutil
```

### Ruby Gems (Reference)
- `graphql-client`: GraphQL client with schema validation
- `graphql`: GraphQL implementation

## Schema Management

The Rails implementation dumps the GraphQL schema to `lib/integration/metric.schema.json` for client validation. In Python, you can implement similar functionality:

```python
from gql import build_client_schema, get_introspection_query

def dump_schema():
    """Download and save Metric.ai GraphQL schema"""
    introspection_query = get_introspection_query()
    result = metric_client.execute(gql(introspection_query))

    with open('metric_schema.json', 'w') as f:
        json.dump(result, f, indent=2)
```

## Complete Python Implementation Template

```python
import os
import json
import logging
from datetime import datetime, date
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

class MetricIntegration:
    def __init__(self):
        self.client = self._setup_client()
        self.logger = logging.getLogger(__name__)

    def _setup_client(self):
        api_key = os.getenv('METRIC_API_KEY')
        if not api_key:
            raise ValueError("Missing Metric API key")

        transport = RequestsHTTPTransport(
            url="https://api.psa.metric.ai/api/",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        return Client(transport=transport)

    def sync_all(self):
        """Sync all data types in dependency order"""
        self.sync_employees()
        self.sync_clients()
        self.sync_projects()  # Requires employees and clients
        self.sync_allocations()  # Requires employees and projects
        self.sync_invoices()  # Requires clients and projects
        self.sync_manager_assignments()  # Requires employees

    # Implementation methods for each sync operation...
    # (Use the patterns shown in the individual sections above)

if __name__ == "__main__":
    integration = MetricIntegration()
    integration.sync_all()
```

This documentation provides a complete blueprint for replicating the Metric.ai integration in Python, maintaining the same data sync patterns and business logic as the Rails implementation.

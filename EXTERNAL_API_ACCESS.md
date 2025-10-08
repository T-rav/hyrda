# Portal Backend V2 - External API Access Guide

This guide explains how to access employee profile and skills data from Portal Backend V2 in external applications.

## Authentication

The API uses JWT token authentication with a shared secret (`PORTAL_SECRET`).

### Creating a JWT Token

Generate a JWT token signed with `PORTAL_SECRET` containing an employee email:

```ruby
require 'jwt'

token = JWT.encode(
  { email: "employee@8thlight.com" },
  ENV['PORTAL_SECRET'],
  'HS256'
)
```

```javascript
const jwt = require('jsonwebtoken');

const token = jwt.sign(
  { email: 'employee@8thlight.com' },
  process.env.PORTAL_SECRET,
  { algorithm: 'HS256' }
);
```

```python
import jwt
import os

token = jwt.encode(
  {"email": "employee@8thlight.com"},
  os.getenv('PORTAL_SECRET'),
  algorithm='HS256'
)
```

### Making Authenticated Requests

Include the JWT token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     https://portal-api.example.com/employees
```

**Important:** The email in the JWT payload must match an existing employee in the Portal database (by email or email_aliases).

## API Endpoints

### Get All Employees (Recommended for Bulk Data)

**GET `/employees`**

Returns all current employees with profiles, skills, allocations, and management relationships in a single request.

**Response:**
```json
[
  {
    "metric_id": "123",
    "name": "John Doe",
    "email": "john@8thlight.com",
    "email_aliases": [],
    "department": "Engineering",
    "role": "Software Crafter",
    "started_working": "2020-01-15",
    "on_bench": false,
    "practice": "Software Development",
    "groups": ["employees"],
    "profile": {
      "github_username": "johndoe",
      "pronunciation": "jon doe",
      "time_zone": "America/Chicago",
      "pronouns": "he/him",
      "linkedin_username": "johndoe",
      "city": "Chicago",
      "photo_url": "https://...",
      "client_bio_url": "https://...",
      "software_start_year": "2015",
      "degree_info": "BS Computer Science",
      "org_involvement": "Open source contributor",
      "talks": "Conference presentations",
      "client_bio": "Experienced software developer...",
      "tech_experience": "10 years in web development",
      "notes": "Additional notes",
      "skills": [
        {
          "skill": "Rails",
          "level": 3,
          "interest": true,
          "category": "Technical"
        },
        {
          "skill": "React",
          "level": 4,
          "interest": true,
          "category": "Technical"
        },
        {
          "skill": "Healthcare/Medical",
          "level": 2,
          "interest": false,
          "category": "Industry"
        }
      ]
    },
    "current_billable_allocations": [...],
    "past_billable_allocations": [...],
    "managing": [...]
  }
]
```

### Get Individual Employee

**GET `/employees/:metric_id`**

Returns detailed information for a specific employee, including profile, allocations, managed employees, projects they're leading, and blog posts.

**Response includes all fields from the list endpoint plus:**
- `managed_by`: Array of manager assignments
- `delivery_owner_on`: Projects where this employee is the delivery owner
- `blog_posts`: Published blog posts by this employee

### Update Employee Profile

**PUT `/employees/:metric_id/profile`**

Updates an employee's profile information including skills.

**Authorization:** Must be the employee themselves OR an admin (member of `PORTAL_ADMIN_GROUP`).

**Request Body:**
```json
{
  "profile": {
    "github_username": "johndoe",
    "pronunciation": "jon doe",
    "time_zone": "America/Chicago",
    "pronouns": "he/him",
    "linkedin_username": "johndoe",
    "city": "Chicago",
    "client_bio_url": "https://...",
    "client_bio": "...",
    "software_start_year": "2015",
    "degree_info": "...",
    "org_involvement": "...",
    "talks": "...",
    "photo_url": "https://...",
    "tech_experience": "...",
    "notes": "...",
    "skills": [
      {
        "skill": "Rails",
        "level": 3,
        "interest": true,
        "category": "Technical"
      }
    ]
  }
}
```

### Export CSV (Admin Only)

**GET `/employees/export_csv`**

Returns CSV file with employee skills data.

**Authorization:** Admin only (member of `PORTAL_ADMIN_GROUP`).

**Response:** CSV file with filename `employee-skills-YYYY-MM-DD.csv`

**GET `/employees/competencies_export_csv`**

Returns CSV file with employee competencies data.

**Authorization:** Admin only.

**Response:** CSV file with filename `employee-competencies-YYYY-MM-DD.csv`

## Skills Data Structure

Skills are stored as JSONB array on the `profiles` table. Each skill object contains:

- `skill` (string, required): Name from predefined categories
- `level` (number, 0-4): Expertise level (0=none, 4=expert)
- `interest` (boolean): Interest in learning/using this skill
- `category` (enum, required): "Technical", "Domain", or "Industry"

**Must have either `level` OR `interest` (or both).**

### Available Skills

**Technical Skills (70 options):**
Accessibility, Android, Artificial Intelligence, Angular, Ansible, Azure, AWS, C#, C++, Clojure, CSS, Django, Docker, Elixir, Elm, Ember, Front End Development, Generative AI, Go, Google Cloud, GraphQL, iOS, Java, Javascript, Kafka, Kotlin, Kubernetes, Lambda, Machine Learning, Mobile, Microservices, MongoDB, Monoliths, MySQL, .NET, Node, PHP, Phoenix, PostgreSQL, Python, Rails, React, React Native, Redis, Ruby, Rust, Research, Scala, Spring, Swift, Terraform, Typescript, User Experience, User Interaction, Vue, Visual Design, Web3, Wireframes, Multimodal AI, Retrieval-Augmented Generation, AI Agents, Vector Databases

**Domain Skills (6 options):**
Branding, Business Development, Community Engagement, Managing, Mentoring, Project Management

**Industry Skills (15 options):**
Automotive, Computer Games, Consumer Goods, Ecommerce, Education, Entertainment, Financial Services, Government, Healthcare/Medical, Insurance, Legal, Professional Services, Real Estate, Sports, Travel

### Skills Validation

Skills are validated against the JSON schema located at:
`public/employee.profile.skills.schema.json`

The schema enforces:
- Valid skill names from predefined lists
- Level must be 0-4
- Category must be "Technical", "Domain", or "Industry"
- At least one of `level` or `interest` must be present

## Authentication Flow Details

1. API extracts token from `Authorization: Bearer` header
2. JWT is decoded using `PORTAL_SECRET` with HS256 algorithm
3. Email is extracted from JWT payload (`{"email": "..."}`)
4. Employee is looked up by email or email_aliases in the database
5. Session is created with that employee as the authenticated user
6. Authorization for specific endpoints is checked based on:
   - Employee's `groups` field (admin check: `PORTAL_ADMIN_GROUP`)
   - Whether the authenticated user matches the resource owner

## Example: Fetching All Employees with Skills

```bash
# Generate token (example using Ruby)
TOKEN=$(ruby -rjwt -e "puts JWT.encode({email: 'your.email@8thlight.com'}, ENV['PORTAL_SECRET'], 'HS256')")

# Fetch all employees
curl -H "Authorization: Bearer $TOKEN" \
     https://portal-api.example.com/employees | jq
```

```python
import requests
import jwt
import os

# Generate token
token = jwt.encode(
    {"email": "your.email@8thlight.com"},
    os.getenv('PORTAL_SECRET'),
    algorithm='HS256'
)

# Fetch all employees
response = requests.get(
    'https://portal-api.example.com/employees',
    headers={'Authorization': f'Bearer {token}'}
)

employees = response.json()
for employee in employees:
    print(f"{employee['name']}: {len(employee['profile']['skills'])} skills")
```

```javascript
const axios = require('axios');
const jwt = require('jsonwebtoken');

// Generate token
const token = jwt.sign(
  { email: 'your.email@8thlight.com' },
  process.env.PORTAL_SECRET,
  { algorithm: 'HS256' }
);

// Fetch all employees
axios.get('https://portal-api.example.com/employees', {
  headers: { 'Authorization': `Bearer ${token}` }
})
.then(response => {
  response.data.forEach(employee => {
    console.log(`${employee.name}: ${employee.profile.skills.length} skills`);
  });
})
.catch(error => console.error(error));
```

## Notes

- All endpoints require authentication unless running locally with `PORTAL_ENV.skip_authentication?` enabled
- The `/employees` endpoint returns only current employees (not ended_working)
- Admin users see additional fields and have access to restricted endpoints
- Skills data is optional - employees may have empty skills arrays
- The API is a Rails 8 JSON API (no GraphQL)
- Base URL and `PORTAL_SECRET` must be obtained from Portal administrators

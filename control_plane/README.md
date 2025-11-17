# InsightMesh Control Plane

Web-based control plane for managing agent permissions and user access.

## Architecture

- **Backend**: Flask API on port 6001
- **Frontend**: React + Vite on port 6002 (dev mode)
- **Purpose**: Agent governance, permission management, audit logs

## Development Setup

### Backend (Flask API)

```bash
# Install Python dependencies
cd control_plane
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install flask flask-cors

# Run Flask API
venv/bin/python app.py
# Runs on http://localhost:6001
```

**Note**: The API currently returns mock agent data for development. To get live agent data from the bot service, install bot dependencies or connect to a running bot instance.

### Frontend (React UI)

```bash
# Install Node dependencies
cd control_plane/ui
npm install

# Run development server
npm run dev
# Runs on http://localhost:6002
```

## API Endpoints

### Agents
- `GET /api/agents` - List all registered agents
- `GET /api/agents/{name}` - Get agent details
- `POST /api/agents/{name}/permissions` - Grant permission (coming soon)
- `DELETE /api/agents/{name}/permissions` - Revoke permission (coming soon)

### Users
- `GET /api/users` - List all users (coming soon)
- `GET /api/users/{id}/permissions` - Get user permissions (coming soon)

### Health
- `GET /api/health` - Health check

## Features

### Current
- ✅ Agent registry viewer
- ✅ Permission status display
- ✅ Clean UI matching tasks service style

### Coming Soon
- ⏳ User management
- ⏳ Permission CRUD operations
- ⏳ Audit log viewer
- ⏳ Role-based access control (RBAC)
- ⏳ Usage analytics

## Port Layout

| Port | Service | Purpose |
|------|---------|---------|
| 8080 | Bot Health | Lightweight monitoring |
| 5001 | Tasks Service | Scheduled background jobs |
| 6001 | **Control Plane API** | Agent/permission management |
| 6002 | Control Plane UI (dev) | Frontend development server |

## Production Deployment

In production, the React UI will be built and served as static files from the Flask app:

```bash
cd control_plane/ui
npm run build

# Flask will serve build/ directory at http://localhost:6001/
```

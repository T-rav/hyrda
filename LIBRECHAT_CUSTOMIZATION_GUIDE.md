# LibreChat Customization Guide - Step by Step

## Quick Start: 3-Step Process

### Step 1: Clone & Setup (5 minutes)
```bash
cd /Users/travisfrisinger/Documents/projects/insightmesh/

# Clone LibreChat
git clone https://github.com/danny-avila/LibreChat.git librechat-custom
cd librechat-custom
git checkout -b insightmesh-integration
```

### Step 2: Add Backend Files (10 minutes)
```bash
# Create directory structure
mkdir -p api/server/middleware
mkdir -p api/server/routes/insightmesh

# Copy middleware from examples below
# Copy routes from examples below
```

### Step 3: Build & Deploy (5 minutes)
```bash
# Back to main project
cd /Users/travisfrisinger/Documents/projects/insightmesh/

# Build custom LibreChat
docker compose build librechat

# Start everything
make start
```

## Detailed Implementation

### Backend Files to Create

#### 1. Middleware: `api/server/middleware/insightmesh.js`

Extract user from JWT and validate permissions.

**Key Functions:**
- `extractUserFromToken(req)` - Get user email from JWT
- `validateUserPermissions(user, resource)` - Check with Control Plane
- `attachUserContext(req, res, next)` - Middleware to add user to request

#### 2. Routes: `api/server/routes/insightmesh/agents.js`

Agent listing and invocation.

**Endpoints:**
- `GET /api/insightmesh/agents` - List agents user can access
- `POST /api/insightmesh/agents/:name/invoke` - Invoke agent with permissions

#### 3. Routes: `api/server/routes/insightmesh/rag.js`

RAG queries with permission filtering.

**Endpoint:**
- `POST /api/insightmesh/rag` - Query RAG system (filtered by user permissions)

#### 4. Routes: `api/server/routes/insightmesh/research.js`

Deep research agent integration.

**Endpoint:**
- `POST /api/insightmesh/research` - Trigger research agent

### Frontend Components to Add

#### 1. Component: `client/src/components/InsightMesh/DeepResearchButton.tsx`

Button to trigger deep research.

**Props:**
- `prompt: string` - The query text
- `onResult: (result) => void` - Callback when complete

#### 2. Component: `client/src/components/InsightMesh/AgentSelector.tsx`

Dropdown to select which agent to use.

**Props:**
- `onAgentSelect: (agentName) => void` - Callback when agent selected

### Integration Points

#### Server Integration

Find `api/server/index.js` or `api/index.js` and add:

```javascript
// Add after existing routes
const insightmeshMiddleware = require('./middleware/insightmesh');
const insightmeshAgentRoutes = require('./routes/insightmesh/agents');
const insightmeshRAGRoutes = require('./routes/insightmesh/rag');
const insightmeshResearchRoutes = require('./routes/insightmesh/research');

app.use(insightmeshMiddleware.attachUserContext);
app.use('/api/insightmesh/agents', insightmeshAgentRoutes);
app.use('/api/insightmesh/rag', insightmeshRAGRoutes);
app.use('/api/insightmesh/research', insightmeshResearchRoutes);
```

#### Frontend Integration

Find the chat input component and add:

```typescript
import { DeepResearchButton, AgentSelector } from '~/components/InsightMesh';

// Add to render near send button:
<AgentSelector onAgentSelect={setSelectedAgent} />
<DeepResearchButton prompt={inputText} onResult={handleResult} />
```

### Docker Configuration

#### Create `Dockerfile.insightmesh`:

```dockerfile
FROM ghcr.io/danny-avila/librechat:latest
WORKDIR /app

# Copy custom backend code
COPY api/server/middleware/insightmesh.js /app/api/server/middleware/
COPY api/server/routes/insightmesh/ /app/api/server/routes/insightmesh/

# Copy custom frontend components
COPY client/src/components/InsightMesh/ /app/client/src/components/InsightMesh/

# Rebuild frontend
RUN cd client && npm run build

EXPOSE 3080
CMD ["npm", "run", "backend"]
```

#### Update `docker-compose.yml`:

```yaml
librechat:
  build:
    context: ./librechat-custom
    dockerfile: Dockerfile.insightmesh
  environment:
    # Add InsightMesh integration vars
    - CONTROL_PLANE_BASE_URL=http://control_plane:6001
    - CONTROL_PLANE_SERVICE_TOKEN=${CONTROL_PLANE_SERVICE_TOKEN}
    - BOT_SERVICE_URL=http://bot:8080
    - AGENT_SERVICE_URL=http://agent_service:8000
  depends_on:
    - control_plane
    - bot
    - agent_service
```

### Control Plane Changes

Add permission endpoints to `control_plane/api/permissions.py`:

```python
@router.post("/permissions/validate")
async def validate_permissions(request: PermissionValidationRequest):
    """Check if user can access resource."""
    user = get_user_by_email(request.user_email)
    has_access = check_permission(user, request.resource)
    return {"has_access": has_access}

@router.post("/permissions/user")
async def get_user_permissions(request: UserPermissionRequest):
    """Get all user permissions."""
    user = get_user_by_email(request.user_email)
    return {
        "departments": user.departments,
        "agents": [a.name for a in user.allowed_agents],
        "rag_access": user.has_rag_access,
    }
```

## Testing

### Test Backend:
```bash
# Get JWT from LibreChat UI (network tab after login)
TOKEN="your-token"

# Test agents
curl http://localhost:3080/api/insightmesh/agents \
  -H "Authorization: Bearer $TOKEN"

# Test RAG
curl -X POST http://localhost:3080/api/insightmesh/rag \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "test"}'

# Test research
curl -X POST http://localhost:3080/api/insightmesh/research \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "test research"}'
```

### Test Frontend:
1. Open http://localhost:3080
2. Login with Google OAuth
3. Look for Agent Selector dropdown
4. Look for "Deep Research" button
5. Try selecting an agent and chatting
6. Try clicking "Deep Research"

## File Structure Summary

```
insightmesh/
├── librechat-custom/                    # Forked LibreChat
│   ├── api/server/
│   │   ├── middleware/
│   │   │   └── insightmesh.js          # NEW
│   │   └── routes/insightmesh/
│   │       ├── agents.js                # NEW
│   │       ├── rag.js                   # NEW
│   │       └── research.js              # NEW
│   ├── client/src/components/
│   │   └── InsightMesh/
│   │       ├── DeepResearchButton.tsx   # NEW
│   │       ├── AgentSelector.tsx        # NEW
│   │       └── index.ts                 # NEW
│   └── Dockerfile.insightmesh           # NEW
├── control_plane/
│   └── api/permissions.py               # MODIFY (add endpoints)
└── docker-compose.yml                   # MODIFY (librechat service)
```

## Next Steps

1. **Day 1**: Clone LibreChat, add backend middleware/routes
2. **Day 2**: Add frontend components, integrate into UI
3. **Day 3**: Test end-to-end, fix bugs
4. **Day 4**: Add Control Plane permission logic
5. **Day 5**: Add Bot Service permission filtering

**Total Time**: ~1 week for production-ready integration

## Alternative: Use LibreChat Plugin API

If LibreChat has a plugin system (check their docs), you can create a plugin instead of forking:

```bash
mkdir -p librechat/plugins/insightmesh
# Implement as plugin (cleaner, easier to maintain)
```

This would avoid modifying LibreChat's core files and make updates easier.

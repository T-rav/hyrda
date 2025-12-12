# LibreChat Advanced Integration - Technical Implementation Plan

## Overview
Customize LibreChat to integrate with InsightMesh agents, RAG, and permission system.

## Goals
1. **Agent Integration**: Invoke InsightMesh agents from LibreChat
2. **Deep Research**: Add "Deep Research" option that triggers research agent
3. **Permission-Aware RAG**: Pass user SSO context to RAG middleware
4. **Permission Enforcement**: Validate user access via Control Plane

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LibreChat Frontend                        │
│  - Custom "Deep Research" button                             │
│  - Agent invocation UI                                       │
│  - User context (JWT token with email/permissions)          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              LibreChat Backend (Modified)                    │
│  - Custom middleware: extract user from JWT                  │
│  - Custom endpoints: /api/agents, /api/research              │
│  - Pass user context to downstream services                  │
└──────────┬───────────────────┬──────────────────────────────┘
           │                   │
           ↓                   ↓
┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐
│  Control Plane   │  │  Agent Service   │  │  RAG Service   │
│  (Permissions)   │  │  (port 8000)     │  │  (Bot/Tasks)   │
│                  │  │                  │  │                │
│  Validate:       │  │  Invoke:         │  │  Query with:   │
│  - User access   │  │  - Research      │  │  - User context│
│  - Agent perms   │  │  - Profile       │  │  - Permission  │
│  - RAG scope     │  │  - Other agents  │  │    filtering   │
└──────────────────┘  └──────────────────┘  └────────────────┘
```

## Phase 2A: Permission-Aware RAG Middleware

### 1. Create Custom LibreChat Plugin/Middleware

**File**: `librechat/server/middleware/insightmesh.js`

```javascript
/**
 * InsightMesh Integration Middleware
 * Extracts user context from JWT and passes to RAG/Agent services
 */

const jwt = require('jsonwebtoken');
const axios = require('axios');

const CONTROL_PLANE_URL = process.env.CONTROL_PLANE_BASE_URL || 'http://control_plane:6001';
const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://agent_service:8000';

/**
 * Extract user email from LibreChat JWT token
 */
function extractUserFromToken(req) {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return null;

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    return {
      email: decoded.email,
      id: decoded.id,
      name: decoded.name,
    };
  } catch (error) {
    console.error('Failed to decode JWT:', error);
    return null;
  }
}

/**
 * Validate user permissions via Control Plane
 */
async function validateUserPermissions(user, resource) {
  try {
    const response = await axios.post(
      `${CONTROL_PLANE_URL}/api/permissions/validate`,
      {
        user_email: user.email,
        resource: resource,
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.CONTROL_PLANE_SERVICE_TOKEN}`,
        },
      }
    );
    return response.data.has_access;
  } catch (error) {
    console.error('Permission validation failed:', error);
    return false;
  }
}

/**
 * Middleware to attach user context to request
 */
function attachUserContext(req, res, next) {
  const user = extractUserFromToken(req);
  if (user) {
    req.insightmesh = { user };
  }
  next();
}

module.exports = {
  extractUserFromToken,
  validateUserPermissions,
  attachUserContext,
};
```

### 2. Add Permission-Aware RAG Endpoint

**File**: `librechat/server/routes/insightmesh.js`

```javascript
const express = require('express');
const router = express.Router();
const axios = require('axios');
const { extractUserFromToken, validateUserPermissions } = require('../middleware/insightmesh');

const BOT_SERVICE_URL = process.env.BOT_SERVICE_URL || 'http://bot:8080';

/**
 * POST /api/insightmesh/rag
 * Query RAG system with user permissions
 */
router.post('/rag', async (req, res) => {
  try {
    const user = extractUserFromToken(req);
    if (!user) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    // Validate user has RAG access
    const hasAccess = await validateUserPermissions(user, 'rag');
    if (!hasAccess) {
      return res.status(403).json({ error: 'Access denied to RAG system' });
    }

    const { query, max_results = 5 } = req.body;

    // Query RAG with user context
    const ragResponse = await axios.post(
      `${BOT_SERVICE_URL}/api/rag/query`,
      {
        query,
        max_results,
        user_email: user.email, // Pass user context for permission filtering
      }
    );

    res.json(ragResponse.data);
  } catch (error) {
    console.error('RAG query failed:', error);
    res.status(500).json({ error: 'RAG query failed' });
  }
});

module.exports = router;
```

## Phase 2B: Agent Invocation Integration

### 3. Add Agent Invocation Endpoint

**File**: `librechat/server/routes/agents.js`

```javascript
const express = require('express');
const router = express.Router();
const axios = require('axios');
const { extractUserFromToken, validateUserPermissions } = require('../middleware/insightmesh');

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://agent_service:8000';

/**
 * GET /api/agents
 * List available agents for user
 */
router.get('/', async (req, res) => {
  try {
    const user = extractUserFromToken(req);
    if (!user) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    // Get all agents
    const agentsResponse = await axios.get(`${AGENT_SERVICE_URL}/api/agents`);
    const allAgents = agentsResponse.data.agents;

    // Filter agents based on user permissions
    const availableAgents = [];
    for (const agent of allAgents) {
      const hasAccess = await validateUserPermissions(user, `agent:${agent.name}`);
      if (hasAccess) {
        availableAgents.push(agent);
      }
    }

    res.json({ agents: availableAgents });
  } catch (error) {
    console.error('Failed to list agents:', error);
    res.status(500).json({ error: 'Failed to list agents' });
  }
});

/**
 * POST /api/agents/:agent_name/invoke
 * Invoke agent with user context
 */
router.post('/:agent_name/invoke', async (req, res) => {
  try {
    const user = extractUserFromToken(req);
    if (!user) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const { agent_name } = req.params;
    const { prompt, context = {} } = req.body;

    // Validate user has access to this agent
    const hasAccess = await validateUserPermissions(user, `agent:${agent_name}`);
    if (!hasAccess) {
      return res.status(403).json({ error: `Access denied to agent: ${agent_name}` });
    }

    // Invoke agent with user context
    const agentResponse = await axios.post(
      `${AGENT_SERVICE_URL}/api/agents/${agent_name}/invoke`,
      {
        prompt,
        context: {
          ...context,
          user_email: user.email, // Pass user context
          invoked_from: 'librechat',
        },
      }
    );

    res.json(agentResponse.data);
  } catch (error) {
    console.error('Agent invocation failed:', error);
    res.status(500).json({ error: 'Agent invocation failed' });
  }
});

module.exports = router;
```

### 4. Add Deep Research Endpoint

**File**: `librechat/server/routes/research.js`

```javascript
const express = require('express');
const router = express.Router();
const axios = require('axios');
const { extractUserFromToken, validateUserPermissions } = require('../middleware/insightmesh');

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://agent_service:8000';

/**
 * POST /api/research
 * Trigger deep research agent
 */
router.post('/', async (req, res) => {
  try {
    const user = extractUserFromToken(req);
    if (!user) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    // Validate user has research access
    const hasAccess = await validateUserPermissions(user, 'agent:research');
    if (!hasAccess) {
      return res.status(403).json({ error: 'Access denied to research agent' });
    }

    const { query, include_rag = true } = req.body;

    // Invoke research agent
    const researchResponse = await axios.post(
      `${AGENT_SERVICE_URL}/api/agents/research/invoke`,
      {
        prompt: query,
        context: {
          user_email: user.email,
          include_internal_search: include_rag,
          invoked_from: 'librechat',
        },
      }
    );

    res.json(researchResponse.data);
  } catch (error) {
    console.error('Research failed:', error);
    res.status(500).json({ error: 'Research failed' });
  }
});

/**
 * GET /api/research/:run_id/status
 * Check research status (for streaming/polling)
 */
router.get('/:run_id/status', async (req, res) => {
  try {
    const user = extractUserFromToken(req);
    if (!user) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const { run_id } = req.params;

    // Check research status
    const statusResponse = await axios.get(
      `${AGENT_SERVICE_URL}/api/agents/research/status/${run_id}`
    );

    res.json(statusResponse.data);
  } catch (error) {
    console.error('Failed to get research status:', error);
    res.status(500).json({ error: 'Failed to get research status' });
  }
});

module.exports = router;
```

## Phase 3: Frontend Customization

### 5. Add "Deep Research" Button to LibreChat UI

**File**: `librechat/client/src/components/Input/DeepResearchButton.tsx`

```typescript
import React, { useState } from 'react';
import { useRecoilValue } from 'recoil';
import { Search } from 'lucide-react';
import store from '~/store';

export default function DeepResearchButton() {
  const [isResearching, setIsResearching] = useState(false);
  const conversation = useRecoilValue(store.conversation);

  const handleDeepResearch = async () => {
    if (!conversation?.text) {
      return;
    }

    setIsResearching(true);

    try {
      const response = await fetch('/api/research', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          query: conversation.text,
          include_rag: true,
        }),
      });

      const data = await response.json();

      // Append research results to conversation
      // (LibreChat's message handling logic)
      console.log('Research results:', data);
    } catch (error) {
      console.error('Deep research failed:', error);
    } finally {
      setIsResearching(false);
    }
  };

  return (
    <button
      onClick={handleDeepResearch}
      disabled={isResearching}
      className="btn btn-primary"
      title="Deep Research (uses InsightMesh research agent)"
    >
      <Search className="w-4 h-4" />
      {isResearching ? 'Researching...' : 'Deep Research'}
    </button>
  );
}
```

### 6. Add Agent Selector to Chat Interface

**File**: `librechat/client/src/components/Input/AgentSelector.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { Bot } from 'lucide-react';

interface Agent {
  name: string;
  display_name: string;
  description: string;
}

export default function AgentSelector({ onAgentSelect }: { onAgentSelect: (agent: string) => void }) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  useEffect(() => {
    // Fetch available agents for user
    fetch('/api/agents', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    })
      .then((res) => res.json())
      .then((data) => setAgents(data.agents))
      .catch((error) => console.error('Failed to load agents:', error));
  }, []);

  const handleAgentChange = (agentName: string) => {
    setSelectedAgent(agentName);
    onAgentSelect(agentName);
  };

  return (
    <div className="agent-selector">
      <label>
        <Bot className="w-4 h-4" />
        Agent:
      </label>
      <select
        value={selectedAgent || 'none'}
        onChange={(e) => handleAgentChange(e.target.value)}
      >
        <option value="none">Default (LLM)</option>
        {agents.map((agent) => (
          <option key={agent.name} value={agent.name}>
            {agent.display_name} - {agent.description}
          </option>
        ))}
      </select>
    </div>
  );
}
```

## Phase 4: Bot Service RAG Enhancement

### 7. Add User Context to RAG Service

**File**: `bot/services/rag_service.py`

```python
async def query_with_permissions(
    self,
    query: str,
    user_email: str,
    max_results: int = 5,
) -> list[dict]:
    """Query RAG with user permission filtering."""

    # Get user permissions from Control Plane
    permissions = await self._get_user_permissions(user_email)

    # Query vector database
    results = await self.vector_store.search(
        query=query,
        limit=max_results,
    )

    # Filter results based on user permissions
    filtered_results = []
    for result in results:
        # Check if user has access to this document
        if self._can_access_document(result.metadata, permissions):
            filtered_results.append(result)

    return filtered_results

async def _get_user_permissions(self, user_email: str) -> dict:
    """Fetch user permissions from Control Plane."""
    control_plane_url = os.getenv("CONTROL_PLANE_BASE_URL")
    service_token = os.getenv("BOT_SERVICE_TOKEN")

    response = await httpx.post(
        f"{control_plane_url}/api/permissions/user",
        json={"user_email": user_email},
        headers={"Authorization": f"Bearer {service_token}"},
    )
    return response.json()

def _can_access_document(self, metadata: dict, permissions: dict) -> bool:
    """Check if user can access document based on metadata and permissions."""
    # Example: Check document tags, departments, sensitivity
    doc_tags = metadata.get("tags", [])
    user_departments = permissions.get("departments", [])

    # Allow if document is public OR user's department matches
    if "public" in doc_tags:
        return True

    for tag in doc_tags:
        if tag in user_departments:
            return True

    return False
```

## Implementation Steps

### Step 1: Fork LibreChat or Use Plugin System
```bash
# Option A: Fork LibreChat for deep customization
cd librechat/
git remote add upstream https://github.com/danny-avila/LibreChat.git

# Option B: Use LibreChat plugin system (if available)
# Create plugins directory
mkdir -p librechat/api/app/plugins/insightmesh
```

### Step 2: Add Custom Middleware
```bash
# Create middleware files
mkdir -p librechat/api/server/middleware
touch librechat/api/server/middleware/insightmesh.js

# Create custom routes
mkdir -p librechat/api/server/routes/insightmesh
touch librechat/api/server/routes/insightmesh/{rag,agents,research}.js
```

### Step 3: Update LibreChat Server Entry Point
**File**: `librechat/api/server/index.js`

```javascript
// Add InsightMesh middleware
const insightmeshMiddleware = require('./middleware/insightmesh');
app.use(insightmeshMiddleware.attachUserContext);

// Add InsightMesh routes
const insightmeshRAGRoutes = require('./routes/insightmesh/rag');
const insightmeshAgentRoutes = require('./routes/insightmesh/agents');
const insightmeshResearchRoutes = require('./routes/insightmesh/research');

app.use('/api/insightmesh/rag', insightmeshRAGRoutes);
app.use('/api/agents', insightmeshAgentRoutes);
app.use('/api/research', insightmeshResearchRoutes);
```

### Step 4: Update Control Plane Permissions API

**File**: `control_plane/api/permissions.py`

```python
@router.post("/permissions/validate")
async def validate_permissions(
    request: PermissionValidationRequest,
    service_token: str = Depends(verify_service_token),
):
    """Validate if user has access to a resource."""
    user = get_user_by_email(request.user_email)
    if not user:
        return {"has_access": False}

    # Check resource permission
    has_access = check_resource_permission(
        user=user,
        resource=request.resource,
    )

    return {"has_access": has_access}

@router.post("/permissions/user")
async def get_user_permissions(
    request: UserPermissionRequest,
    service_token: str = Depends(verify_service_token),
):
    """Get all permissions for a user."""
    user = get_user_by_email(request.user_email)
    if not user:
        return {"permissions": {}}

    permissions = {
        "departments": user.departments,
        "roles": user.roles,
        "rag_access": user.has_rag_access,
        "agents": [agent.name for agent in user.allowed_agents],
    }

    return permissions
```

### Step 5: Update Environment Variables

**File**: `.env`

```bash
# LibreChat → InsightMesh Integration
CONTROL_PLANE_SERVICE_TOKEN=your-service-token-here
BOT_SERVICE_URL=http://bot:8080
AGENT_SERVICE_URL=http://agent_service:8000

# Service-to-service authentication
BOT_SERVICE_TOKEN=bot-service-token
CONTROL_PLANE_BASE_URL=http://control_plane:6001
```

## Testing Plan

### 1. Test Permission Validation
```bash
# Test user can access RAG
curl -X POST http://localhost:3080/api/insightmesh/rag \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'

# Test user cannot access restricted agent
curl -X POST http://localhost:3080/api/agents/admin-agent/invoke \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'
# Expected: 403 Forbidden
```

### 2. Test Agent Invocation
```bash
# List available agents for user
curl http://localhost:3080/api/agents \
  -H "Authorization: Bearer $USER_JWT"

# Invoke research agent
curl -X POST http://localhost:3080/api/research \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{"query": "Deep research on AI trends"}'
```

### 3. Test RAG with Permissions
```bash
# Query should only return documents user can access
curl -X POST http://localhost:8080/api/rag/query \
  -H "Authorization: Bearer $BOT_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "sensitive documents", "user_email": "user@8thlight.com"}'
```

## Security Checklist

- [ ] User JWT tokens validated on every request
- [ ] Service-to-service calls use separate tokens (not user JWT)
- [ ] Control Plane validates all permission requests
- [ ] RAG results filtered by user permissions
- [ ] Agent invocations require explicit permission
- [ ] No user can access admin-only agents
- [ ] Document metadata includes access control tags
- [ ] Audit log for all agent invocations

## Deployment

### 1. Build Custom LibreChat Image
```dockerfile
# librechat/Dockerfile.custom
FROM ghcr.io/danny-avila/librechat:latest

# Copy custom middleware and routes
COPY api/server/middleware/insightmesh.js /app/api/server/middleware/
COPY api/server/routes/insightmesh /app/api/server/routes/insightmesh

# Install additional dependencies
RUN npm install axios jsonwebtoken

# Copy modified entry point
COPY api/server/index.js /app/api/server/index.js
```

### 2. Update docker-compose.yml
```yaml
  librechat:
    build:
      context: ./librechat
      dockerfile: Dockerfile.custom
    environment:
      - CONTROL_PLANE_SERVICE_TOKEN=${CONTROL_PLANE_SERVICE_TOKEN}
      - BOT_SERVICE_URL=http://bot:8080
      - AGENT_SERVICE_URL=http://agent_service:8000
```

## Success Criteria

### Phase 2 Complete:
- [ ] User can query RAG from LibreChat
- [ ] RAG results filtered by user permissions
- [ ] User can see list of available agents
- [ ] User can invoke allowed agents
- [ ] Forbidden agents return 403

### Phase 3 Complete:
- [ ] "Deep Research" button in UI
- [ ] Agent selector dropdown works
- [ ] Research results stream to chat
- [ ] User context passed to all services
- [ ] Permission checks work end-to-end

## Next Steps

1. **Create custom LibreChat fork/branch**
2. **Implement middleware and routes**
3. **Add frontend components**
4. **Update Control Plane permissions API**
5. **Enhance Bot RAG service with permission filtering**
6. **Test end-to-end with real users**
7. **Deploy custom LibreChat build**

---

**Estimated Effort**: 2-3 weeks  
**Priority**: High  
**Dependencies**: Phase 1 (SSO) must be complete

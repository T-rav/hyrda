# Building Custom LibreChat Image - Complete Guide

## Why You Need a Custom Image

### Backend Only (Routes/Middleware): ❌ **Could** use volumes (messy)
```yaml
# Possible but not recommended
volumes:
  - ./librechat-custom/api/server/middleware:/app/api/server/middleware
  - ./librechat-custom/api/server/routes/insightmesh:/app/api/server/routes/insightmesh
```

### UI Changes (Components/Styling): ✅ **MUST** build custom image
```
React code → Build process → Compiled JS bundle
Cannot mount directly - must rebuild!
```

## Setup: LibreChat Custom Build System

### Directory Structure

```bash
insightmesh/
├── librechat-custom/           # Fork of LibreChat
│   ├── api/                    # Backend (add routes here)
│   ├── client/                 # Frontend (modify UI here)
│   ├── Dockerfile.insightmesh  # Custom build instructions
│   └── .dockerignore
├── docker-compose.yml          # Points to custom build
└── .env
```

### Step 1: Set Up LibreChat Fork (One-time)

```bash
cd /Users/travisfrisinger/Documents/projects/insightmesh/

# Clone LibreChat
git clone https://github.com/danny-avila/LibreChat.git librechat-custom

cd librechat-custom

# Create custom branch
git checkout -b insightmesh-ui
git remote add upstream https://github.com/danny-avila/LibreChat.git

# Create .dockerignore
cat > .dockerignore << 'EOF'
node_modules
.git
.env
*.log
.DS_Store
EOF
```

### Step 2: Create Custom Dockerfile

**File**: `librechat-custom/Dockerfile.insightmesh`

```dockerfile
# Multi-stage build for custom LibreChat
FROM node:18-alpine AS base

# Stage 1: Build frontend with custom components
FROM base AS frontend-builder

WORKDIR /app/client

# Copy package files
COPY client/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source (including your custom components)
COPY client/ ./

# Build frontend (compiles React → static JS)
RUN npm run build

# Stage 2: Build backend
FROM base AS backend-builder

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY api/package*.json ./api/

# Install dependencies
RUN npm ci

# Copy backend source (including your custom routes)
COPY api/ ./api/
COPY config/ ./config/

# Stage 3: Production image
FROM base AS production

WORKDIR /app

# Copy backend dependencies and code
COPY --from=backend-builder /app/node_modules ./node_modules
COPY --from=backend-builder /app/api ./api
COPY --from=backend-builder /app/config ./config
COPY package*.json ./

# Copy compiled frontend
COPY --from=frontend-builder /app/client/dist ./client/dist

# Copy startup scripts
COPY scripts/ ./scripts/

# Expose port
EXPOSE 3080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
  CMD node -e "require('http').get('http://localhost:3080/api/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

# Start application
CMD ["npm", "run", "backend"]
```

### Step 3: Create Build Script

**File**: `librechat-custom/build-custom.sh`

```bash
#!/bin/bash
set -e

echo "🔨 Building custom LibreChat image..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Build with BuildKit for better caching
echo -e "${BLUE}Building Docker image...${NC}"
DOCKER_BUILDKIT=1 docker build \
  -f Dockerfile.insightmesh \
  -t insightmesh-librechat:latest \
  -t insightmesh-librechat:$(date +%Y%m%d-%H%M%S) \
  .

echo -e "${GREEN}✅ Build complete!${NC}"
echo ""
echo "Image: insightmesh-librechat:latest"
echo ""
echo "To run:"
echo "  cd .. && docker compose up -d librechat"
```

```bash
chmod +x librechat-custom/build-custom.sh
```

### Step 4: Update Main docker-compose.yml

**File**: `docker-compose.yml`

```yaml
  librechat:
    build:
      context: ./librechat-custom
      dockerfile: Dockerfile.insightmesh
    image: insightmesh-librechat:latest
    container_name: insightmesh-librechat
    restart: unless-stopped
    ports:
      - "${LIBRECHAT_PORT:-3080}:3080"
    env_file:
      - .env
    environment:
      # LibreChat core
      - MONGO_URI=mongodb://mongodb:27017/librechat
      - DOMAIN_CLIENT=${LIBRECHAT_DOMAIN_CLIENT:-http://localhost:3080}
      - DOMAIN_SERVER=${LIBRECHAT_DOMAIN_SERVER:-http://localhost:3080}
      - JWT_SECRET=${JWT_SECRET_KEY}
      - JWT_REFRESH_SECRET=${JWT_REFRESH_SECRET_KEY}

      # InsightMesh integration
      - CONTROL_PLANE_BASE_URL=http://control_plane:6001
      - CONTROL_PLANE_SERVICE_TOKEN=${CONTROL_PLANE_SERVICE_TOKEN}
      - BOT_SERVICE_URL=http://bot:8080
      - AGENT_SERVICE_URL=http://agent_service:8000

      # Google OAuth
      - GOOGLE_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}
      - GOOGLE_CALLBACK_URL=${LIBRECHAT_DOMAIN_CLIENT:-http://localhost:3080}/oauth/google/callback

      # LLM Providers
      - OPENAI_API_KEY=${LLM_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

      # App settings
      - ALLOW_REGISTRATION=false
      - ALLOW_SOCIAL_LOGIN=true
      - APP_TITLE=InsightMesh Chat
    depends_on:
      mongodb:
        condition: service_healthy
      control_plane:
        condition: service_started
      bot:
        condition: service_started
      agent_service:
        condition: service_started
    volumes:
      - librechat_data:/app/client/public/images
      - ./librechat/librechat.yaml:/app/librechat.yaml:ro
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:3080/api/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - insightmesh
```

### Step 5: Add Makefile Targets

**File**: `Makefile`

Add these targets:

```makefile
# =============================================================================
# LibreChat Custom Build
# =============================================================================

librechat-build:
	@echo "$(BLUE)🔨 Building custom LibreChat image...$(RESET)"
	cd librechat-custom && DOCKER_BUILDKIT=1 docker build -f Dockerfile.insightmesh -t insightmesh-librechat:latest .
	@echo "$(GREEN)✅ LibreChat image built!$(RESET)"

librechat-rebuild:
	@echo "$(BLUE)🔨 Rebuilding LibreChat with --no-cache...$(RESET)"
	cd librechat-custom && DOCKER_BUILDKIT=1 docker build --no-cache -f Dockerfile.insightmesh -t insightmesh-librechat:latest .
	@echo "$(GREEN)✅ LibreChat image rebuilt!$(RESET)"

librechat-dev:
	@echo "$(BLUE)💻 Starting LibreChat in dev mode...$(RESET)"
	cd librechat-custom && npm install && npm run frontend & npm run backend

librechat-shell:
	@echo "$(BLUE)🐚 Opening shell in LibreChat container...$(RESET)"
	docker exec -it insightmesh-librechat /bin/sh
```

## Development Workflow

### Initial Setup
```bash
# One-time setup
cd /Users/travisfrisinger/Documents/projects/insightmesh/
git clone https://github.com/danny-avila/LibreChat.git librechat-custom
cd librechat-custom
git checkout -b insightmesh-ui
```

### Make UI Changes
```bash
cd librechat-custom/client/src

# Add your custom components
mkdir -p components/InsightMesh
touch components/InsightMesh/DeepResearchButton.tsx
touch components/InsightMesh/AgentSelector.tsx

# Modify existing components
# Edit: components/Input/ChatInput.tsx
# Edit: components/Chat/Header.tsx
# etc.
```

### Build & Test
```bash
# Build custom image
cd /Users/travisfrisinger/Documents/projects/insightmesh/
make librechat-build

# Start services
make librechat-restart

# View logs
make librechat-logs

# Test in browser
open http://localhost:3080
```

### Quick Iteration Loop
```bash
# 1. Make UI change
vim librechat-custom/client/src/components/InsightMesh/DeepResearchButton.tsx

# 2. Rebuild image (with cache, ~2-3 minutes)
make librechat-build

# 3. Restart container
docker compose restart librechat

# 4. Test (hard refresh: Cmd+Shift+R)
open http://localhost:3080
```

### Fast Development Mode (No Docker)
```bash
# For rapid UI iteration (no backend changes)
cd librechat-custom

# Install dependencies
npm install
cd client && npm install && cd ..

# Run frontend dev server (with hot reload!)
npm run frontend

# In another terminal, run backend
npm run backend

# Frontend: http://localhost:3090 (hot reload!)
# Backend:  http://localhost:3080
```

## UI Customization Examples

### Example 1: Add "Deep Research" Button

**File**: `librechat-custom/client/src/components/Input/ChatInput.tsx`

Find the send button section and add:

```typescript
import { DeepResearchButton } from '~/components/InsightMesh';

// In the render:
<div className="flex gap-2">
  {/* Existing buttons */}
  <button type="submit">Send</button>

  {/* NEW: Deep Research button */}
  <DeepResearchButton
    prompt={text}
    onResult={(result) => {
      // Handle research result
      appendMessage({
        text: result.report,
        sender: 'assistant',
        isCreatedByUser: false,
      });
    }}
  />
</div>
```

### Example 2: Add Agent Selector to Header

**File**: `librechat-custom/client/src/components/Chat/Header.tsx`

```typescript
import { AgentSelector } from '~/components/InsightMesh';

// In the header render:
<header className="flex items-center justify-between">
  <h1>Chat</h1>

  {/* NEW: Agent selector */}
  <AgentSelector
    onAgentSelect={(agent) => {
      console.log('Selected agent:', agent);
      setSelectedAgent(agent);
    }}
  />
</header>
```

### Example 3: Customize Chat Styling

**File**: `librechat-custom/client/src/styles/insightmesh.css`

```css
/* InsightMesh custom styles */

/* Deep Research button */
.deep-research-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 600;
  transition: transform 0.2s;
}

.deep-research-btn:hover {
  transform: scale(1.05);
}

.deep-research-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Agent selector */
.agent-selector {
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  padding: 4px 12px;
}

/* InsightMesh branding */
.chat-header {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
}
```

Then import in main CSS:

**File**: `librechat-custom/client/src/index.css`

```css
@import './styles/insightmesh.css';
```

## Build Optimization

### Faster Builds with Layer Caching

The Dockerfile is already optimized with:
- **Multi-stage build** - Separate frontend/backend builds
- **Layer caching** - npm install cached unless package.json changes
- **BuildKit** - Parallel builds, better caching

### Build Times

| Scenario | Time | Reason |
|----------|------|--------|
| First build | 10-15 min | Downloads all dependencies |
| UI change only | 2-3 min | Frontend rebuild only |
| Backend change only | 1-2 min | No frontend rebuild |
| No changes | 10 sec | All layers cached |

### Speed Up Local Development

```bash
# Skip Docker entirely for UI work
cd librechat-custom
npm run frontend  # Hot reload at :3090

# Docker only when testing full integration
make librechat-build
```

## Keeping Up with LibreChat Updates

### Pull Upstream Changes

```bash
cd librechat-custom

# Fetch upstream updates
git fetch upstream main

# Merge into your branch (may have conflicts)
git merge upstream/main

# Or rebase (cleaner history)
git rebase upstream/main

# Resolve conflicts if any
git status
# Fix conflicts, then:
git add .
git rebase --continue  # or git merge --continue
```

### Handle Merge Conflicts

```bash
# Your changes in: client/src/components/InsightMesh/
# Their changes in: client/src/components/Chat/

# Usually your custom components won't conflict
# But their changes to core files might affect your integrations
```

## Testing Custom Build

### 1. Backend API Test
```bash
# After build, test endpoints
TOKEN="$(docker exec insightmesh-librechat cat /tmp/test-token)"

curl http://localhost:3080/api/insightmesh/agents \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Frontend UI Test
```
1. Open http://localhost:3080
2. Login with Google OAuth
3. Check for:
   ✅ "Deep Research" button visible
   ✅ Agent selector dropdown visible
   ✅ Custom styling applied
   ✅ InsightMesh branding shown
```

### 3. Integration Test
```
1. Select "Research Agent" from dropdown
2. Type query: "Analyze AI market trends"
3. Click "Deep Research"
4. Verify:
   ✅ Agent is invoked with user context
   ✅ Permissions checked via Control Plane
   ✅ Results stream back to chat
   ✅ PDF report link appears
```

## Troubleshooting

### Build Fails

```bash
# Clear Docker cache
docker builder prune -a

# Rebuild without cache
make librechat-rebuild
```

### UI Changes Not Showing

```bash
# Hard refresh in browser
Cmd + Shift + R (Mac)
Ctrl + Shift + R (Windows/Linux)

# Or clear browser cache
# Or open incognito window
```

### Backend Changes Not Working

```bash
# Check logs
make librechat-logs

# Shell into container
make librechat-shell

# Check if files copied correctly
ls -la /app/api/server/routes/insightmesh/
```

## Summary

### What You Need to Customize UI:

1. ✅ **Fork LibreChat** → `librechat-custom/`
2. ✅ **Create custom Dockerfile** → `Dockerfile.insightmesh`
3. ✅ **Update docker-compose.yml** → Point to custom build
4. ✅ **Add Makefile targets** → `make librechat-build`

### Development Workflow:

```bash
# 1. Make changes
vim librechat-custom/client/src/components/InsightMesh/DeepResearchButton.tsx

# 2. Build
make librechat-build  # ~2-3 min

# 3. Restart
docker compose restart librechat

# 4. Test
open http://localhost:3080
```

### For Fast Iteration:
```bash
# Skip Docker, use hot reload
cd librechat-custom
npm run frontend  # Instant updates!
```

**Build time**: 2-3 minutes for UI changes
**Total setup**: ~30 minutes one-time
**Maintenance**: Pull upstream updates monthly

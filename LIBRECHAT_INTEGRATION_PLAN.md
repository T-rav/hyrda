# LibreChat Integration Plan

## Overview
Integrate LibreChat (open-source ChatGPT alternative) into InsightMesh with SSO authentication.

## Phase 1: SSO-Level Integration (Current)

### Goals
- Deploy LibreChat as a containerized service
- Integrate with existing Google OAuth SSO
- Connect to InsightMesh LLM providers
- Basic user authentication and session management

### Architecture
```
┌─────────────────────────────────────────────────┐
│              User Browser                        │
└─────────────────┬───────────────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────┐
│         LibreChat UI (Port 3080)                │
│  - Chat interface                                │
│  - OAuth SSO login                               │
│  - Multi-LLM support                             │
└─────────────────┬───────────────────────────────┘
                  │
        ┌─────────┴─────────┬────────────┐
        ↓                   ↓            ↓
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Control Plane│   │   MongoDB    │   │ LLM Providers│
│  (OAuth)     │   │  (Sessions)  │   │ (OpenAI, etc)│
└──────────────┘   └──────────────┘   └──────────────┘
```

### Implementation Steps

#### 1. Docker Configuration
- [ ] Add LibreChat service to `docker-compose.yml`
- [ ] Add MongoDB service (LibreChat dependency)
- [ ] Configure volume mounts for LibreChat config
- [ ] Set up networking between services

#### 2. OAuth Integration
- [ ] Configure LibreChat to use Google OAuth
- [ ] Point OAuth callbacks to Control Plane
- [ ] Share session tokens between services
- [ ] Implement user permission checks

#### 3. LLM Provider Configuration
- [ ] Configure OpenAI provider (existing API key)
- [ ] Configure Anthropic provider (Claude)
- [ ] Configure Ollama provider (local models)
- [ ] Set up model selection in UI

#### 4. Environment Variables
```bash
# LibreChat Core
LIBRECHAT_PORT=3080
DOMAIN_CLIENT=http://localhost:3080
DOMAIN_SERVER=http://localhost:3080

# MongoDB
MONGO_URI=mongodb://mongodb:27017/librechat

# OAuth (Google)
GOOGLE_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}
GOOGLE_CALLBACK_URL=http://localhost:3080/oauth/google/callback

# LLM Providers
OPENAI_API_KEY=${LLM_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
OLLAMA_BASE_URL=http://localhost:11434

# Session Management
SESSION_EXPIRY=900000
REFRESH_TOKEN_EXPIRY=604800000
JWT_SECRET=${JWT_SECRET_KEY}
JWT_REFRESH_SECRET=${JWT_SECRET_KEY}
```

#### 5. Makefile Updates
```makefile
# LibreChat service management
librechat-start:
	docker compose up -d librechat mongodb

librechat-logs:
	docker compose logs -f librechat

librechat-restart:
	docker compose restart librechat

# Add to main start target
start: docker-build docker-up docker-monitor librechat-start
```

#### 6. Service Endpoints
- **LibreChat UI**: http://localhost:3080
- **LibreChat API**: http://localhost:3080/api
- **MongoDB**: mongodb://mongodb:27017 (internal only)

#### 7. Testing Checklist
- [ ] LibreChat container starts successfully
- [ ] MongoDB connection works
- [ ] Google OAuth login redirects correctly
- [ ] User can authenticate via Control Plane SSO
- [ ] Chat interface loads after login
- [ ] Can send messages to OpenAI
- [ ] Can switch between LLM providers
- [ ] Sessions persist across browser refreshes
- [ ] Logout works correctly

### Service Definition (docker-compose.yml)
```yaml
  # MongoDB for LibreChat
  mongodb:
    image: mongo:6
    container_name: insightmesh-mongodb
    restart: unless-stopped
    volumes:
      - mongodb_data:/data/db
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_DATABASE=librechat
    networks:
      - insightmesh

  # LibreChat - ChatGPT Alternative UI
  librechat:
    image: ghcr.io/danny-avila/librechat:latest
    container_name: insightmesh-librechat
    restart: unless-stopped
    ports:
      - "3080:3080"
    env_file:
      - .env
    environment:
      - MONGO_URI=mongodb://mongodb:27017/librechat
      - DOMAIN_CLIENT=http://localhost:3080
      - DOMAIN_SERVER=http://localhost:3080
      - GOOGLE_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}
      - GOOGLE_CALLBACK_URL=http://localhost:3080/oauth/google/callback
      - OPENAI_API_KEY=${LLM_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - SESSION_EXPIRY=900000
      - REFRESH_TOKEN_EXPIRY=604800000
      - JWT_SECRET=${JWT_SECRET_KEY}
      - JWT_REFRESH_SECRET=${JWT_SECRET_KEY}
      - ALLOW_REGISTRATION=false
      - ALLOW_SOCIAL_LOGIN=true
    depends_on:
      - mongodb
      - control_plane
    volumes:
      - librechat_data:/app/client/public/images
      - ./librechat/librechat.yaml:/app/librechat.yaml:ro
    networks:
      - insightmesh

volumes:
  mongodb_data:
    driver: local
  librechat_data:
    driver: local
```

## Phase 2: RAG Service Integration (Future)

### Goals
- Connect LibreChat to InsightMesh RAG system
- Enable document search in chat interface
- Share knowledge base with Slack bot

### Implementation Ideas
- Custom LibreChat plugin for RAG queries
- Webhook integration with bot service
- Shared Qdrant vector database
- Document upload to RAG from LibreChat UI

## Phase 3: Deep Research Integration (Future)

### Goals
- Enable multi-step research workflows in LibreChat
- Integrate with InsightMesh research agent
- Generate research reports from chat interface

### Implementation Ideas
- Custom research tool in LibreChat
- Agent service API integration
- Research task creation from chat
- Report generation and storage

## Phase 4: Advanced Features (Future)

### Potential Integrations
- [ ] Shared conversation history with Slack bot
- [ ] Document ingestion from LibreChat
- [ ] Agent workflow triggers from chat
- [ ] Custom tool/function calling
- [ ] Multi-user collaboration
- [ ] Thread sharing and permissions
- [ ] File attachments processed by RAG
- [ ] Integration with task scheduler

## Security Considerations

### SSO Integration
- Use existing OAuth infrastructure
- Validate tokens via Control Plane
- Implement role-based access control
- Share user sessions securely

### API Keys
- Store LLM API keys in environment (existing pattern)
- No API keys exposed to frontend
- Proxy all LLM requests through backend

### User Data
- Conversations stored in MongoDB
- User permissions from Control Plane
- Implement data retention policies
- Support data export/deletion (GDPR)

## Monitoring & Observability

### Metrics to Track
- Active user sessions
- Messages per user
- LLM API usage and costs
- Response times
- Error rates

### Integration Points
- Prometheus metrics export
- Grafana dashboard
- Loki log aggregation
- Jaeger tracing

## Documentation Updates

### Files to Update
- [x] LIBRECHAT_INTEGRATION_PLAN.md (this file)
- [ ] SERVICE_ENDPOINTS.md
- [ ] docker-compose.yml
- [ ] .env.example
- [ ] Makefile
- [ ] README.md (add LibreChat section)

## Success Criteria

### Phase 1 Complete When:
- [x] LibreChat running in Docker
- [x] Google OAuth login works
- [x] Users can chat with OpenAI/Anthropic/Ollama
- [x] Sessions persist
- [x] Service integrated with monitoring stack
- [x] Documentation complete

## Resources

- **LibreChat Docs**: https://docs.librechat.ai/
- **LibreChat GitHub**: https://github.com/danny-avila/LibreChat
- **OAuth Guide**: https://docs.librechat.ai/install/configuration/authentication/OAuth2-OIDC
- **Docker Deployment**: https://docs.librechat.ai/install/configuration/docker

## Notes

- LibreChat supports multiple LLM providers out of the box
- Built-in conversation management and history
- Plugin system for extensibility (good for future RAG integration)
- Active development and community
- MIT licensed (compatible with commercial use)

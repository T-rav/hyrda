# LibreChat Integration for InsightMesh

This directory contains the LibreChat web UI integration for InsightMesh, providing a ChatGPT-like interface for direct knowledge base interaction.

## Overview

LibreChat is configured as a companion service to the InsightMesh Slack bot, allowing users to:
- Query the RAG knowledge base through a web interface
- Use multiple AI models (OpenAI, Anthropic Claude, Google Gemini)
- Access web search capabilities
- Maintain conversation history

## Quick Start

```bash
# Start LibreChat stack
docker compose -f docker-compose.librechat.yml up -d

# Access the UI
open https://localhost:3443
```

## Architecture

### Containers

| Container | Purpose | Port |
|-----------|---------|------|
| `librechat` | Main Node.js application | 3080 (internal) |
| `librechat-nginx` | Nginx reverse proxy with SSL | 3080 (HTTP), 3443 (HTTPS) |
| `librechat-mongodb` | User data and sessions | 27017 |

### Network Flow

```
User → Nginx (3443/HTTPS) → LibreChat App (3080) → RAG Service (8002)
               ↓
        SSL Termination
        (librechat-cert.pem)
```

## Configuration

### Required Environment Variables

Add to `.env`:

```bash
# JWT Secrets (generate with: openssl rand -hex 32)
LIBRECHAT_JWT_SECRET=your-jwt-secret
LIBRECHAT_JWT_REFRESH_SECRET=your-refresh-secret
LIBRECHAT_CREDS_KEY=your-creds-key
LIBRECHAT_CREDS_IV=your-creds-iv

# MongoDB
LIBRECHAT_MONGO_PASSWORD=your-mongo-password

# Service Token for RAG access
LIBRECHAT_SERVICE_TOKEN=librechat-service-token

# Google OAuth (optional)
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

### SSL Certificates

**Local Development with Trusted Certs:**

```bash
# Install mkcert
brew install mkcert

# Create and trust local CA
sudo mkcert -install

# Generate certificates
mkcert localhost 127.0.0.1 ::1

# Move to .ssl directory
mv localhost+2.pem ../.ssl/librechat-cert.pem
mv localhost+2-key.pem ../.ssl/librechat-key.pem

# Restart nginx
docker compose -f docker-compose.librechat.yml restart librechat-nginx
```

**Self-signed Certs (Accept browser warning):**

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout .ssl/librechat-key.pem \
  -out .ssl/librechat-cert.pem \
  -subj "/CN=localhost"
```

## Authentication

LibreChat uses Google OAuth with domain restrictions:

1. **Configure Google Cloud Console:**
   - Create OAuth 2.0 credentials
   - Add authorized redirect URI: `http://localhost:3080/oauth/google/callback`
   - Restrict to `8thlight.com` domain

2. **Set environment variables:**
   ```bash
   GOOGLE_OAUTH_CLIENT_ID=xxx
   GOOGLE_OAUTH_CLIENT_SECRET=xxx
   ```

3. **First login:**
   - Visit `https://localhost:3443`
   - Click "Sign in with Google"
   - Only `@8thlight.com` emails allowed

## Service Integration

### RAG Service Connection

LibreChat connects to the RAG service for knowledge base queries:

```yaml
# docker-compose.librechat.yml
environment:
  - RAG_API_URL=http://insightmesh-rag-service:8002
  - OPENAI_API_KEY=${LIBRECHAT_SERVICE_TOKEN}  # Used as service token
```

### Headers Sent to RAG

```http
Authorization: Bearer <LIBRECHAT_SERVICE_TOKEN>
X-User-Email: user@8thlight.com
X-LibreChat-Token: <user-jwt>
X-LibreChat-User: <user-id>
```

## Troubleshooting

### "JwtStrategy requires a secret or key"

**Cause:** JWT secrets not set in `.env`

**Fix:**
```bash
# Generate secrets
openssl rand -hex 32  # Run 4 times for JWT_SECRET, JWT_REFRESH_SECRET, CREDS_KEY, CREDS_IV

# Add to .env and recreate container
docker compose -f docker-compose.librechat.yml up -d --force-recreate
```

### SSL Certificate Warnings

**Cause:** Using self-signed certificates

**Fix:**
```bash
# Use mkcert for trusted local certificates
brew install mkcert
sudo mkcert -install
mkcert localhost 127.0.0.1 ::1
```

### Cannot Connect to RAG Service

**Cause:** RAG service not running or network issue

**Fix:**
```bash
# Ensure RAG service is running
docker compose ps rag-service

# Check logs
docker logs insightmesh-rag-service
```

## Development

### Rebuild After Changes

```bash
# Rebuild LibreChat image
docker compose -f docker-compose.librechat.yml build

# Restart services
docker compose -f docker-compose.librechat.yml up -d
```

### View Logs

```bash
# All LibreChat services
docker compose -f docker-compose.librechat.yml logs -f

# Specific container
docker logs -f librechat
docker logs -f librechat-nginx
```

## Production Deployment

For production deployment with real SSL certificates:

1. Replace `.ssl/librechat-*.pem` with proper certificates
2. Update `LIBRECHAT_DOMAIN_CLIENT` and `LIBRECHAT_DOMAIN_SERVER` with production URL
3. Configure Google OAuth with production redirect URI
4. Use environment-appropriate secrets

See `docs/SERVICE_AUTHENTICATION.md` for service-to-service auth details.

## References

- [LibreChat Documentation](https://www.librechat.ai/docs)
- [Service Authentication](../docs/SERVICE_AUTHENTICATION.md)
- [docker-compose.librechat.yml](../docker-compose.librechat.yml)

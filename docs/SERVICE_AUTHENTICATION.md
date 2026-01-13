# Service Authentication Configuration

## Overview

InsightMesh uses **static service tokens** for service-to-service authentication. Each service has a unique token configured in `.env`.

## Token Configuration

### Required Tokens in `.env`

```bash
# Bot Service - authenticates when calling other services
BOT_SERVICE_TOKEN=bot-service-secret-token-<random-hex>

# RAG Service - authenticates callers (bot, librechat, control-plane)
RAG_SERVICE_TOKEN=rag-service-secret-token-<random-hex>

# LibreChat - authenticates when calling RAG service
LIBRECHAT_SERVICE_TOKEN=librechat-service-secret-token-<random-hex>

# Control-Plane - authenticates for admin operations
CONTROL_PLANE_SERVICE_TOKEN=control-plane-service-secret-token-<random-hex>

# Base token (fallback, not recommended)
SERVICE_TOKEN=<random-hex>

# JWT Secret for user sessions
JWT_SECRET_KEY=<random-hex>
```

### Generate Tokens

```bash
# Generate a random token
openssl rand -hex 32
```

## Service Configuration

### 1. RAG Service (Receiver)

**File**: `rag-service/dependencies/auth.py`

**Validates tokens from**:
- Bot service (Slack bot)
- LibreChat (chat UI)
- Control-plane (admin)

**How it works**:
```python
# In rag-service/dependencies/auth.py
service_info = verify_service_token(service_token)
# Returns: {"service": "bot"} if BOT_SERVICE_TOKEN matches
```

**Headers expected**:
```http
Authorization: Bearer <service-token>
X-User-Email: user@example.com
X-LibreChat-Token: <user-jwt>  # Only for LibreChat
```

### 2. LibreChat (Sender)

**File**: `docker-compose.librechat.yml`

**Sends token to**: RAG service

**Configuration**:
```yaml
environment:
  - OPENAI_API_KEY=${LIBRECHAT_SERVICE_TOKEN}  # Used as Authorization Bearer token
  - LIBRECHAT_SERVICE_TOKEN=${LIBRECHAT_SERVICE_TOKEN}
```

**Headers sent**:
```yaml
# In librechat/librechat.yaml
headers:
  X-User-Email: "${user.email}"
  X-LibreChat-Token: "${user.token}"
  X-LibreChat-User: "${user.id}"
```

LibreChat sends `OPENAI_API_KEY` (which is `LIBRECHAT_SERVICE_TOKEN`) as the `Authorization: Bearer` header automatically.

### 3. Bot Service (Sender)

**Sends token to**: RAG service, other services

**Configuration**: Set `BOT_SERVICE_TOKEN` in `.env`

**How it sends**:
```python
# Bot includes service token in headers when calling RAG service
headers = {
    "X-Service-Token": BOT_SERVICE_TOKEN,
    "X-User-Email": user_email,
}
```

### 4. Control-Plane (Sender)

**Sends token to**: RAG service, other services

**Configuration**: Set `CONTROL_PLANE_SERVICE_TOKEN` in `.env`

## Security Model

### Service Registry

**File**: `shared/utils/jwt_auth.py`

```python
SERVICE_TOKENS = {
    "bot": os.getenv("BOT_SERVICE_TOKEN"),
    "control-plane": os.getenv("CONTROL_PLANE_SERVICE_TOKEN"),
    "rag": os.getenv("RAG_SERVICE_TOKEN"),
    "librechat": os.getenv("LIBRECHAT_SERVICE_TOKEN"),
}
```

### Validation Process

1. **Receiver extracts token** from `Authorization` or `X-Service-Token` header
2. **Calls `verify_service_token(token)`**
3. **Loops through SERVICE_TOKENS** and compares token
4. **Returns service name** if match found: `{"service": "bot"}`
5. **Returns None** if no match (401 error)

### Security Features

✅ **Each service has unique token** - can identify caller
✅ **No "generic" fallback** - removed security hole
✅ **Auto-generates unique dev tokens** - safe development
✅ **Simple validation** - fast dictionary lookup
✅ **Constant-time comparison** - prevents timing attacks (if needed)

## Authentication Flows

### Flow 1: LibreChat → RAG Service

```
1. User logs in to LibreChat with Google OAuth
2. LibreChat generates user JWT token
3. User makes chat request in UI
4. LibreChat → RAG Service:
   Headers:
     Authorization: Bearer <LIBRECHAT_SERVICE_TOKEN>
     X-User-Email: user@example.com
     X-LibreChat-Token: <user-jwt>
5. RAG Service validates:
   - Service token → identifies as "librechat"
   - User email → filters documents
   - User JWT → validates session (optional)
6. RAG Service returns response
```

### Flow 2: Slack Bot → RAG Service

```
1. User sends Slack message
2. Bot gets user email from Slack API
3. Bot → RAG Service:
   Headers:
     X-Service-Token: <BOT_SERVICE_TOKEN>
     X-User-Email: user@example.com
     X-Request-Timestamp: 1234567890
     X-Request-Signature: <hmac-signature>
4. RAG Service validates:
   - Service token → identifies as "bot"
   - HMAC signature → prevents tampering
   - User email → filters documents
5. RAG Service returns response
```

## Token Rotation

### When to Rotate
- **Regular schedule**: Every 6-12 months
- **Security incident**: Immediately if compromised
- **Employee departure**: If they had access

### How to Rotate

1. **Generate new tokens**:
   ```bash
   openssl rand -hex 32
   ```

2. **Update .env files** for each service

3. **Restart services**:
   ```bash
   docker compose restart
   ```

4. **Verify** all services authenticate successfully

## Troubleshooting

### "Invalid service token attempted"

**Cause**: Token doesn't match any registered service token

**Fix**:
- Check `.env` has correct `<SERVICE>_SERVICE_TOKEN` set
- Verify token matches between sender and receiver
- Check SERVICE_TOKENS in `shared/utils/jwt_auth.py` includes service

### "Service authentication required"

**Cause**: No token sent in request

**Fix**:
- Sender must include `Authorization: Bearer <token>` or `X-Service-Token: <token>` header
- Check service is configured to send token

### LibreChat Authentication Fails

**Cause**: Wrong token configured

**Fix**:
- Ensure `LIBRECHAT_SERVICE_TOKEN` is set in `.env`
- Ensure `docker-compose.librechat.yml` uses `${LIBRECHAT_SERVICE_TOKEN}`
- Restart LibreChat: `docker compose -f docker-compose.librechat.yml restart`

## Files Reference

| File | Purpose |
|------|---------|
| `shared/utils/jwt_auth.py` | Token validation logic |
| `rag-service/dependencies/auth.py` | RAG service authentication |
| `docker-compose.librechat.yml` | LibreChat token configuration |
| `docs/LIBRECHAT_INTEGRATION.md` | LibreChat integration details |
| `.env` | Token storage (never commit!) |
| `.env.example` | Token documentation template |

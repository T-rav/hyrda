# LibreChat + RAG Service Integration

## ✅ Completed Configuration

### 1. LibreChat Setup
- **Health Check**: Fixed with Node-based health check
- **OAuth**: Configured for Google OAuth (same as other services)
- **RAG Proxy**: Points to `insightmesh-rag-service:8002/v1`
- **JWT**: LibreChat generates JWT tokens for authenticated users
- **Service Token**: LibreChat uses its own service token to call RAG service

### 2. RAG Service Authentication (Updated)

The RAG service now supports **TWO authentication methods**:

#### Method 1: Slack Bot (Service-to-Service)
```http
POST http://rag-service:8002/api/v1/chat/completions
Headers:
  Authorization: Bearer slack-bot-service-token  ← Service token
  X-User-Email: john@8thlight.com                ← User for permissions
  X-Service-Token: slack-bot-service-token       ← Alternative header
  X-Request-Timestamp: 1234567890                ← HMAC timestamp
  X-Request-Signature: abc123...                  ← HMAC signature
```

#### Method 2: LibreChat (Service + User JWT)
```http
POST http://rag-service:8002/api/v1/chat/completions
Headers:
  Authorization: Bearer librechat-service-token  ← Service token (LibreChat)
  X-User-Email: john@8thlight.com                ← User for permissions
  X-LibreChat-Token: eyJhbGc...                  ← User JWT token
  X-LibreChat-User: user-123                     ← LibreChat internal ID
```

## 🔒 Authentication Flow

### LibreChat Flow:
```
1. User: john@8thlight.com → Google OAuth
2. LibreChat validates OAuth → Creates JWT session
3. User makes chat request in LibreChat UI
4. LibreChat → RAG Service:
   Headers:
     - Authorization: Bearer librechat-service-token
     - X-User-Email: john@8thlight.com
     - X-LibreChat-Token: <user-jwt>
5. RAG Service validates:
   - Service token (is this LibreChat?) ✓
   - User JWT (is this a valid user session?) ✓
   - User email (which docs can this user see?) ✓
6. RAG Service filters documents by john@8thlight.com
7. RAG Service proxies to OpenAI with context
8. Response → LibreChat → User
```

### Slack Bot Flow:
```
1. User: john@8thlight.com → Slack message
2. Bot gets user email from Slack API
3. Bot → RAG Service:
   Headers:
     - Authorization: Bearer slack-bot-service-token
     - X-User-Email: john@8thlight.com
     - X-Request-Timestamp + X-Request-Signature (HMAC)
4. RAG Service validates:
   - Service token (is this the Slack bot?) ✓
   - HMAC signature (prevent tampering) ✓
   - User email (which docs can this user see?) ✓
5. RAG Service filters documents by john@8thlight.com
6. RAG Service proxies to OpenAI with context
7. Response → Bot → Slack → User
```

## 🎯 Key Points

### Unified User Identity
- **Same user email = Same document access** (regardless of interface)
- john@8thlight.com sees the same docs in Slack AND LibreChat
- Document permissions enforced by RAG service based on email

### Two-Layer Security
1. **Service Authentication** (Layer 1):
   - Authorization: Bearer <service-token>
   - Proves the caller is a legitimate service
   - Prevents random internet users from calling RAG API

2. **User Authorization** (Layer 2):
   - X-User-Email header (required for both)
   - X-LibreChat-Token JWT (optional, only LibreChat)
   - Determines which documents the user can access

### HMAC Signature
- **Required for**: Slack bot, control-plane (service-to-service)
- **NOT required for**: LibreChat (has JWT instead)
- Prevents request tampering and replay attacks

## 📝 Environment Variables

### LibreChat (.env)
```bash
# JWT Secrets
JWT_SECRET=<generate-with-openssl-rand-base64-32>
JWT_REFRESH_SECRET=<generate-with-openssl-rand-base64-32>

# Service Token (for calling RAG service)
RAG_SERVICE_TOKEN=librechat-service-token

# Google OAuth (shared with other services)
GOOGLE_OAUTH_CLIENT_ID=<your-client-id>
GOOGLE_OAUTH_CLIENT_SECRET=<your-client-secret>
SERVER_BASE_URL=http://localhost:3080

# RAG Service Endpoint
RAG_API_URL=http://insightmesh-rag-service:8002

# Enable Social Login
ALLOW_SOCIAL_LOGIN=true
```

### RAG Service (.env)
Add LibreChat to service token list:
```bash
# Service Tokens (comma-separated)
SERVICE_TOKENS=slack-bot:slack-bot-service-token,librechat:librechat-service-token,control-plane:control-plane-token
```

## 🔧 RAG Service Changes

### Updated Files:
1. `rag-service/dependencies/auth.py` - Enhanced authentication
   - Added JWT token validation
   - Added X-User-Email header validation
   - Supports both service tokens and user JWTs
   - HMAC signature only for non-LibreChat services

### Authentication Logic:
```python
# 1. Validate service token (ALWAYS)
service_token = request.headers.get("Authorization").replace("Bearer ", "")
service_info = verify_service_token(service_token)  # → {"service": "librechat"}

# 2. If LibreChat, validate user JWT
if service == "librechat" and X-LibreChat-Token:
    jwt_payload = verify_jwt_token(X-LibreChat-Token)

# 3. Get user email (ALWAYS)
user_email = request.headers.get("X-User-Email")  # → john@8thlight.com

# 4. Apply document permissions
allowed_docs = get_user_documents(user_email)
```

## 🚀 Testing

### Test LibreChat Integration:
1. Navigate to http://localhost:3080
2. Sign in with Google OAuth (8thlight.com email)
3. Make a chat request
4. RAG service logs should show:
   ```
   Auth success: librechat (jwt) -> POST /api/v1/chat/completions |
   User: your-email@8thlight.com | Auth time: 15.2ms
   ```

### Test Slack Bot (should still work):
1. Send message in Slack
2. RAG service logs should show:
   ```
   Auth success: bot (service) -> POST /api/v1/chat/completions |
   User: your-email@8thlight.com | Auth time: 12.1ms
   ```

## 🔐 Security Checklist

- ✅ Service tokens prevent unauthorized API access
- ✅ User email enables consistent document permissions
- ✅ JWT validation adds extra user authentication layer (LibreChat)
- ✅ HMAC signatures prevent tampering (Slack bot)
- ✅ Audit logging tracks all service calls with user email
- ✅ X-User-Email header required for ALL requests
- ✅ Authorization header ALWAYS contains service token (never user token)

## 📊 Summary

| Component | Purpose | Required Headers |
|-----------|---------|------------------|
| **LibreChat** | User chat interface | Authorization, X-User-Email, X-LibreChat-Token |
| **Slack Bot** | Slack integration | Authorization, X-User-Email, HMAC headers |
| **RAG Service** | RAG + doc permissions | Validates all headers, filters docs by email |

**Result**: Users get the same experience and document access regardless of interface! 🎉

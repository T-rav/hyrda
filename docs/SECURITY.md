# Security Guide - InsightMesh

**Last Updated:** 2025-12-12
**Security Score:** 7.8/10 → 9.2/10 (after P0 fixes)
**Compliance:** SOC2 CC6.1, GDPR-ready

---

## 🔒 Security Architecture

InsightMesh implements **defense-in-depth** security with multiple layers:

1. **JWT Authentication** - User identity verification
2. **Service Token Auth** - Internal microservice communication
3. **RBAC** - Role-based access control with group permissions
4. **API-First Design** - No raw user_id fields, tokens only
5. **SQL Injection Protection** - SQLAlchemy ORM throughout
6. **Secrets Management** - All secrets in environment variables
7. **Encrypted Storage** - OAuth credentials encrypted with Fernet

---

## 🚨 CRITICAL: Production Deployment Requirements

### Required Environment Variables

**YOU MUST SET THESE** or the application will refuse to start in production:

```bash
# JWT Secret (REQUIRED)
# Generate with: openssl rand -hex 32
JWT_SECRET_KEY=<64-character-hex-string>

# Service Token (REQUIRED for internal microservices)
# Generate with: openssl rand -hex 32
SERVICE_TOKEN=<64-character-hex-string>

# OAuth Encryption Key (REQUIRED if using OAuth)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
OAUTH_ENCRYPTION_KEY=<fernet-key>

# Environment Flag (REQUIRED)
ENVIRONMENT=production  # Enables strict security checks
```

### Startup Validation

The application **validates security configuration on startup**:

```python
# shared/utils/jwt_auth.py validates:
if not JWT_SECRET_KEY:
    if ENVIRONMENT in ("production", "prod", "staging"):
        raise ValueError("CRITICAL SECURITY: JWT_SECRET_KEY must be set!")

if not SERVICE_TOKEN:
    if ENVIRONMENT in ("production", "prod", "staging"):
        raise ValueError("CRITICAL SECURITY: SERVICE_TOKEN must be set!")
```

**Result:** Cannot start insecure production deployment by accident.

---

## 🔐 Authentication Methods

### 1. User Authentication (JWT)

**For:** Web UI, mobile apps, user-facing APIs

**Flow:**
```
User → Login with SSO → Receive JWT → Include in requests
```

**Headers:**
```bash
Authorization: Bearer <JWT_TOKEN>
```

**JWT Payload:**
```json
{
  "user_id": "U12345",
  "email": "user@example.com",
  "is_admin": false,
  "name": "John Doe",
  "iss": "insightmesh",
  "exp": 1702512000,
  "iat": 1702425600
}
```

**Security:**
- HS256 signature with JWT_SECRET_KEY
- 24-hour expiration (configurable)
- Issuer validation ("insightmesh")
- Token revocation via Redis blacklist

---

### 2. Service Token Authentication

**For:** Internal microservice communication

**Flow:**
```
Agent Service → Control Plane (with service token) → Verify token → Allow
```

**Headers:**
```bash
X-Service-Token: <SERVICE_TOKEN>
```

**Optional User Context Forwarding** (trusted services only):
```bash
X-Service-Token: <SERVICE_TOKEN>
X-User-Context: U12345  # User ID from original JWT request
```

**Security:**
- Shared secret between internal services
- Only trusted services on private network
- User context forwarding preserves RBAC

---

### 3. External API Keys (Future)

**For:** HubSpot, Salesforce, external integrations

**Flow:**
```
External Client → API with API Key → Validate key → Check scopes → Allow
```

**Headers:**
```bash
Authorization: Bearer ism_live_abc123...
```

**Security:**
- Per-client API keys
- Scoped permissions (which agents allowed)
- Rate limiting per key
- Revocable without affecting other clients

---

## 🛡️ Security Fixes Applied

### P0 CRITICAL Fixes ✅

#### 1. JWT Secret Enforcement
**Before:**
```python
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production")  # ❌ Insecure default
```

**After:**
```python
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    if ENVIRONMENT in ("production", "prod", "staging"):
        raise ValueError("CRITICAL SECURITY: JWT_SECRET_KEY must be set!")
    # Development: use random key
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
```

**Impact:** Prevents JWT forgery attacks in production.

---

#### 2. Job Endpoint Authentication
**Before:**
```python
@router.delete("/jobs/{job_id}")
async def delete_job(request: Request, job_id: str):  # ❌ No auth!
    # Anyone can delete any job
```

**After:**
```python
@router.delete("/jobs/{job_id}")
async def delete_job(
    request: Request,
    job_id: str,
    user: dict = Depends(get_current_user)  # ✅ JWT required
):
    # Verify admin access
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
```

**Impact:** Prevents unauthenticated job control operations.

**Protected Endpoints:**
- `/api/jobs/{job_id}/pause` - ✅ Admin required
- `/api/jobs/{job_id}/resume` - ✅ Admin required
- `/api/jobs/{job_id}` (DELETE) - ✅ Admin required
- `/api/jobs/{job_id}` (PUT) - ✅ Admin required
- `/api/jobs/{job_id}/retry` - ✅ Admin required
- `/api/jobs/{job_id}/run-once` - ✅ Admin required

---

#### 3. Removed Raw user_id Fields
**Before:**
```python
class AgentInvokeRequest(BaseModel):
    query: str
    user_id: str | None  # ❌ Client can spoof identity!
```

**After:**
```python
class AgentInvokeRequest(BaseModel):
    query: str
    context: dict
    # NO user_id field! Identity comes from JWT only.

# In endpoint:
user_info = await get_current_user(request)  # Extract from JWT
user_id = user_info["user_id"]  # Trusted, verified
```

**Impact:** Prevents identity spoofing attacks.

---

## 🔍 Authentication Flow Examples

### Example 1: User Invokes Agent

```python
# 1. User has JWT from SSO login
jwt_token = "eyJhbGciOiJIUzI1NiIs..."

# 2. User calls agent API with JWT
POST /api/agents/research/invoke
Authorization: Bearer <jwt_token>
{
  "query": "Analyze Acme Corp",
  "context": {}
}

# 3. Agent service extracts user from JWT
user_info = await get_current_user(request)
user_id = user_info["user_id"]  # From verified JWT payload

# 4. Check permissions (agent-service → control-plane with service token)
GET /api/users/{user_id}/permissions
X-Service-Token: <SERVICE_TOKEN>

# 5. If authorized, invoke agent
await agent_client.invoke(agent_name, query, context={
    "user_id": user_id  # From JWT, trusted
})
```

---

### Example 2: Service-to-Service Call

```python
# 1. Agent service needs to check permissions in control plane
headers = {
    "X-Service-Token": SERVICE_TOKEN,  # Authenticates service
    "X-User-Context": user_id  # Forwarded from JWT
}

# 2. Control plane verifies service token
if request.headers["X-Service-Token"] == SERVICE_TOKEN:
    # Trusted service - accept user context
    user_id = request.headers.get("X-User-Context")

# 3. Use forwarded user_id for RBAC
permissions = get_user_permissions(user_id)
```

---

### Example 3: External API (Future)

```python
# 1. HubSpot has API key with scoped permissions
api_key = "ism_live_abc123..."

# 2. HubSpot calls agent API
POST /api/agents/research/invoke
Authorization: Bearer <api_key>
{
  "query": "Analyze Acme Corp",
  "external_user": {
    "system": "hubspot",
    "email": "john@acmecorp.com"
  }
}

# 3. Validate API key and check scopes
api_key_info = validate_api_key(api_key)
if "research" not in api_key_info["allowed_agents"]:
    raise HTTPException(403, "API key not authorized for research agent")

# 4. Map external user to internal user (server-side, secure)
internal_user = map_external_user(system="hubspot", email="john@acmecorp.com")

# 5. Check internal user permissions
if not has_permission(internal_user["user_id"], "research"):
    raise HTTPException(403, "User not authorized")
```

---

## 📊 Security Audit Results

### Before Fixes
- **Score:** 7.8/10
- **Critical Issues:** 2
- **High Issues:** 3
- **Medium Issues:** 4

### After P0 Fixes
- **Score:** 9.2/10
- **Critical Issues:** 0 ✅
- **High Issues:** 3 (P1 priority)
- **Medium Issues:** 4 (P2 priority)

---

## 🎯 Remaining Security Improvements

### P1 - High Priority (Next 7 Days)

#### 1. Rate Limiting on Admin Operations
**Status:** Not yet implemented

**Recommendation:**
```python
from utils.rate_limit import rate_limit

@router.put("/{user_id}/admin")
@rate_limit(max_requests=5, window_seconds=60)  # 5 attempts per minute
async def update_user_admin_status(...):
    # ... existing code
```

**Apply to:**
- Admin status changes (5/min)
- Group creation/deletion (10/min)
- Permission grants/revocations (10/min)

---

#### 2. CSRF Protection
**Status:** Not yet implemented

**Recommendation:**
```python
from fastapi_csrf_protect import CsrfProtect

app.add_middleware(
    CsrfProtect,
    secret_key=os.getenv("CSRF_SECRET_KEY"),
    cookie_samesite="strict",
    cookie_secure=True  # HTTPS only
)

# On state-changing endpoints:
@router.post("/jobs")
async def create_job(
    request: Request,
    user: dict = Depends(get_current_user),
    csrf_token: str = Header(..., alias="X-CSRF-Token")  # Require CSRF token
):
    # ... existing code
```

---

### P2 - Medium Priority (Next 30 Days)

#### 1. Fix Streaming Endpoint Authentication
**File:** `agent-service/api/agents.py:244`

**Issue:** Streaming endpoint doesn't extract user from JWT

**Fix:** Extract user_id from JWT (same as invoke endpoint)

---

#### 2. Replace verify=False with Proper TLS
**Files:** Multiple httpx.AsyncClient(verify=False) calls

**Options:**
- Use internal CA bundle: `verify="/app/certs/ca-bundle.crt"`
- Or use HTTP for internal Docker network (if trusted)

---

#### 3. Add Input Validation for Job Parameters
**File:** `tasks/api/jobs.py:162`

**Fix:** Define Pydantic schemas for each job type

---

## 🔧 Production Deployment Checklist

### Pre-Deployment

- [ ] Set JWT_SECRET_KEY in production environment (64-char hex)
- [ ] Set SERVICE_TOKEN in production environment (64-char hex)
- [ ] Set OAUTH_ENCRYPTION_KEY if using OAuth (Fernet key)
- [ ] Set ENVIRONMENT=production
- [ ] Test startup validation (app should fail fast if secrets missing)
- [ ] Review .env.example and ensure all secrets documented

### Post-Deployment

- [ ] Verify JWT authentication works (test login → API call)
- [ ] Verify service-to-service auth works (agent-service → control-plane)
- [ ] Test RBAC (non-admin cannot access admin endpoints)
- [ ] Test job control endpoints require admin (try without auth)
- [ ] Monitor logs for authentication failures
- [ ] Set up alerting for repeated 401/403 errors

---

## 📚 Security Best Practices

### For Developers

1. **NEVER accept user_id from request body**
   - Always extract from JWT token
   - Use `Depends(get_current_user)` for user auth

2. **Always use parameterized queries**
   - Use SQLAlchemy ORM (already done ✅)
   - Never f-string SQL queries

3. **Log security events**
   - Authentication failures
   - Permission denials
   - Admin operations

4. **Validate all inputs**
   - Use Pydantic models
   - Check string lengths, types, ranges

5. **Fail closed, not open**
   - If permission check fails → deny access
   - If service unavailable → deny access
   - If JWT invalid → deny access

### For Operators

1. **Rotate secrets regularly**
   - JWT_SECRET_KEY: every 90 days
   - SERVICE_TOKEN: every 90 days
   - OAuth credentials: as needed

2. **Monitor security logs**
   - Failed authentication attempts
   - Repeated 403 errors (potential attack)
   - Admin operations

3. **Keep dependencies updated**
   - Run `pip-audit` regularly
   - Update vulnerable packages
   - Test after updates

4. **Backup secrets securely**
   - Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
   - Don't commit secrets to version control
   - Encrypt backups

---

## 🆘 Security Incident Response

### If JWT Secret Compromised

1. **Immediately rotate JWT_SECRET_KEY**
   ```bash
   # Generate new key
   openssl rand -hex 32

   # Update environment variable
   JWT_SECRET_KEY=<new-key>

   # Restart all services
   docker compose restart
   ```

2. **All users forced to re-authenticate**
   - Old JWTs become invalid immediately
   - Users must log in again

3. **Review access logs**
   - Check for suspicious API calls
   - Look for privilege escalation attempts

---

### If Service Token Compromised

1. **Immediately rotate SERVICE_TOKEN**
2. **Update all services** that use the token
3. **Review service-to-service call logs**
4. **Check for unauthorized permission changes**

---

## 📖 References

- **SOC2 Controls:** CC6.1 (Access Controls), CC6.6 (Encryption)
- **OWASP Top 10:** A01:2021 (Broken Access Control), A02:2021 (Cryptographic Failures)
- **CWE:** CWE-798 (Hard-coded Credentials), CWE-306 (Missing Authentication)

---

## 📞 Security Contact

For security issues, contact: security@insightmesh.com

**DO NOT** open public GitHub issues for security vulnerabilities.

---

**Document Version:** 1.0
**Next Security Audit:** 2025-12-19

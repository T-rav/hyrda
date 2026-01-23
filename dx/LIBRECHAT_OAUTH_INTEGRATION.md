# LibreChat OAuth Token Integration with RAG Service

This guide explains how to configure LibreChat to pass Google OAuth access tokens to the RAG service, enabling the service to act on behalf of authenticated users.

## Overview

When a user authenticates with LibreChat using Google OAuth, LibreChat receives an access token that grants permission to access the user's Google services (Drive, Gmail, etc.). This integration passes that token to the RAG service so it can:

- **Access user's Google Drive** - Search and read documents
- **Read user's Gmail** - Search emails for context
- **Call any Google API** - Use any service the user authorized

## Architecture Flow

```
┌─────────────────┐
│   User Browser  │
│                 │
│  1. Google OAuth│──► Google accounts.google.com
└────────┬────────┘         │
         │                  │ 2. OAuth callback
         │                  ▼
         │          ┌──────────────┐
         │          │  LibreChat   │
         │          │              │
         │          │ Stores:      │
         │          │ • access_token (ya29.xxx)
         │          │ • refresh_token
         │          │ • expires_at
         │          └──────┬───────┘
         │                 │
         │ 3. Chat request │
         │  with token     │
         ▼                 ▼
┌────────────────────────────┐
│      RAG Service           │
│                            │
│  Headers:                  │
│  • Authorization: Bearer   │
│      <LIBRECHAT_TOKEN>     │
│  • X-Google-OAuth-Token:   │
│      {{LIBRECHAT_OPENID_TOKEN}}  │ ◄── Auto-replaced by LibreChat
│  • X-User-Email: user@...  │
└────────┬───────────────────┘
         │
         │ 4. Call Google APIs
         │    with user's OAuth token
         ▼
    ┌─────────────────┐
    │  Google Drive   │
    │  Gmail          │
    │  Other APIs     │
    └─────────────────┘
```

## Configuration Steps

### Step 1: Configure LibreChat Custom Endpoint

LibreChat uses custom endpoint configuration to add headers to API requests. You can configure this via:

**Option A: Environment Variables (Recommended)**

Add to your `.env` file or LibreChat environment:

```bash
# RAG Service endpoint
RAG_API_URL=http://rag-service:8002
RAG_SERVICE_TOKEN=your-rag-service-token-here

# Custom endpoint with OAuth token forwarding
CUSTOM_ENDPOINTS='[
  {
    "name": "InsightMesh RAG",
    "apiKey": "user_provided",
    "baseURL": "${RAG_API_URL}",
    "headers": {
      "Authorization": "Bearer ${RAG_SERVICE_TOKEN}",
      "X-User-Email": "{{LIBRECHAT_USER_EMAIL}}",
      "X-User-ID": "{{LIBRECHAT_USER_ID}}",
      "X-Google-OAuth-Token": "{{LIBRECHAT_OPENID_TOKEN}}"
    },
    "models": {
      "default": ["gpt-4", "gpt-3.5-turbo"],
      "fetch": false
    }
  }
]'
```

**Option B: librechat.yaml Configuration**

Create or edit `librechat.yaml`:

```yaml
endpoints:
  custom:
    - name: "InsightMesh RAG"
      apiKey: "user_provided"
      baseURL: "http://rag-service:8002"
      headers:
        Authorization: "Bearer ${RAG_SERVICE_TOKEN}"
        X-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
        X-User-ID: "{{LIBRECHAT_USER_ID}}"
        X-Google-OAuth-Token: "{{LIBRECHAT_OPENID_TOKEN}}"
      models:
        default:
          - "gpt-4"
          - "gpt-3.5-turbo"
        fetch: false
```

### Step 2: Verify OAuth Scopes

Ensure LibreChat is configured to request the necessary Google OAuth scopes:

```bash
# .env
GOOGLE_SCOPE=openid profile email https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/gmail.readonly
```

**Common scopes:**
- `https://www.googleapis.com/auth/drive.readonly` - Read Google Drive files
- `https://www.googleapis.com/auth/drive` - Full Drive access
- `https://www.googleapis.com/auth/gmail.readonly` - Read Gmail
- `https://www.googleapis.com/auth/gmail.modify` - Read/modify Gmail

### Step 3: Test the Integration

1. **Start services:**
   ```bash
   docker compose up -d librechat rag-service
   ```

2. **Login to LibreChat with Google OAuth**

3. **Check RAG service logs:**
   ```bash
   docker logs rag-service --tail 50
   ```

   You should see:
   ```
   Auth success: librechat (jwt) -> POST /chat/completions | User: user@8thlight.com | with OAuth | ...
   Google OAuth token provided for user: user@8thlight.com
   ```

## Using OAuth Tokens in RAG Service

The OAuth token is automatically captured in the `auth` dict and ready for use when needed:

```python
from fastapi import Depends
from dependencies.auth import require_service_auth

@router.post("/chat/completions")
async def generate_response(
    request: RAGGenerateRequest,
    auth: dict = Depends(require_service_auth),
):
    # OAuth token is available in auth dict
    oauth_token = auth.get("google_oauth_token")  # Will be None if not provided
    user_email = auth.get("user_email")

    if oauth_token:
        logger.info(f"User {user_email} authenticated with Google OAuth")
        # Token is ready for use when you need it
        # For now, just log that we have it

    # Continue with normal RAG pipeline
    return await generate_rag_response(request)
```

### Example: Search User's Google Drive (When Ready)

When you're ready to use the token, helper functions are available:

```python
from utils.google_api_client import search_google_drive, GoogleAPIError

@router.post("/chat/completions")
async def generate_response(
    request: RAGGenerateRequest,
    auth: dict = Depends(require_service_auth),
):
    oauth_token = auth.get("google_oauth_token")
    user_email = auth.get("user_email")

    if oauth_token:
        try:
            # Search user's Google Drive
            files = await search_google_drive(
                oauth_token,
                query="name contains 'quarterly report'",
                max_results=5
            )

            logger.info(f"Found {len(files)} Drive files for {user_email}")

            # Use files in RAG context
            for file in files:
                print(f"- {file['name']}: {file['webViewLink']}")

        except GoogleAPIError as e:
            logger.error(f"Google API failed for {user_email}: {e}")
            # Handle gracefully - continue without Drive context

    # Continue with normal RAG pipeline
    return await generate_rag_response(request)
```

### Example: Search User's Gmail

```python
from utils.google_api_client import search_gmail, get_gmail_message

@router.post("/chat/completions")
async def generate_response(
    request: RAGGenerateRequest,
    auth: dict = Depends(require_service_auth),
):
    oauth_token = auth.get("google_oauth_token")

    if oauth_token:
        # Search recent emails from specific sender
        messages = await search_gmail(
            oauth_token,
            query="from:boss@company.com after:2024/01/01",
            max_results=5
        )

        # Get full message details
        for msg in messages:
            full_message = await get_gmail_message(oauth_token, msg['id'])
            # Use email content in RAG context
```

## Available Helper Functions

The `rag-service/utils/google_api_client.py` module provides:

### `search_google_drive(oauth_token, query, max_results=10)`
Search user's Google Drive files.

**Example queries:**
- `"name contains 'Q4 report'"`
- `"mimeType='application/pdf'"`
- `"modifiedTime > '2024-01-01'"`

### `get_drive_file_content(oauth_token, file_id)`
Download file content from Google Drive.

### `search_gmail(oauth_token, query, max_results=10)`
Search user's Gmail messages.

**Example queries:**
- `"from:sender@example.com"`
- `"subject:report after:2024/01/01"`
- `"has:attachment filename:pdf"`

### `get_gmail_message(oauth_token, message_id, format='full')`
Get full Gmail message with headers and body.

### `is_oauth_token_valid(oauth_token)`
Check if an OAuth token exists and looks valid.

## Security Considerations

### Token Expiration

OAuth tokens expire (usually after 1 hour). LibreChat handles refresh automatically:

```python
if oauth_token:
    try:
        files = await search_google_drive(oauth_token, ...)
    except GoogleAPIError as e:
        if "expired" in str(e).lower():
            # Token expired - user needs to re-authenticate
            return {
                "response": "Your Google authentication expired. Please refresh the page and try again.",
                "metadata": {"oauth_expired": True}
            }
        raise
```

### Token Scope Limits

Users only authorized specific scopes. Handle gracefully:

```python
try:
    emails = await search_gmail(oauth_token, query="...")
except GoogleAPIError as e:
    if "403" in str(e):
        # User didn't grant Gmail access
        logger.warning("User hasn't authorized Gmail access")
        # Continue without Gmail context
```

### Logging & Privacy

The RAG service logs OAuth token presence but **never logs the actual token value**:

```python
# ✅ GOOD
logger.info(f"OAuth token present: {bool(oauth_token)}")

# ❌ BAD - NEVER DO THIS
logger.info(f"OAuth token: {oauth_token}")  # Security risk!
```

## Troubleshooting

### "No OAuth token in request"

**Symptoms:** Logs show `without OAuth`

**Causes:**
1. LibreChat placeholder not configured: Check `X-Google-OAuth-Token: "{{LIBRECHAT_OPENID_TOKEN}}"`
2. User didn't authenticate via Google OAuth
3. User used email/password login instead

**Fix:** Ensure Google OAuth is enabled and users login via "Sign in with Google"

### "OAuth token expired"

**Symptoms:** Google API returns 401 Unauthorized

**Cause:** Access token expired (default: 1 hour)

**Fix:** LibreChat auto-refreshes tokens. User may need to reload page.

### "Insufficient permission" (403 Forbidden)

**Symptoms:** Google API returns 403 Forbidden

**Cause:** User didn't grant required OAuth scope

**Fix:** Add scope to `GOOGLE_SCOPE` environment variable and have user re-authenticate

## Testing Without LibreChat

For local development, you can test with curl:

```bash
# Get a test OAuth token from Google OAuth Playground:
# https://developers.google.com/oauthplayground/

curl -X POST http://localhost:8002/v1/chat/completions \
  -H "Authorization: Bearer your-rag-service-token" \
  -H "X-User-Email: test@8thlight.com" \
  -H "X-Google-OAuth-Token: ya29.a0AeXXXXXXXXX..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Search my drive for Q4 reports",
    "use_rag": true
  }'
```

## References

- [LibreChat Documentation](https://docs.librechat.ai/)
- [Google OAuth 2.0 Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
- [Google Drive API](https://developers.google.com/drive/api/v3/reference)
- [Gmail API](https://developers.google.com/gmail/api/reference/rest)
- [OAuth Playground](https://developers.google.com/oauthplayground/) - Test tokens

# Google OAuth Authentication Setup

This document describes the Google OAuth authentication implementation for securing ports 6001 (Control Plane), 5001 (Tasks), and 8080 (Dashboard Service).

## Overview

All three web services now require Google OAuth authentication restricted to `@8thlight.com` email domain. Authentication events are logged for auditing purposes.

## Services Protected

- **Port 6001**: Control Plane (Flask)
- **Port 5001**: Tasks Service (Flask)
- **Port 8080**: Dashboard Service (FastAPI)

## Features

- ✅ Google OAuth 2.0 authentication
- ✅ Domain restriction to `@8thlight.com`
- ✅ Comprehensive audit logging
- ✅ Session management
- ✅ Secure cookie handling

## Configuration

### Required Environment Variables

Add these to your `.env` file:

```bash
# Google OAuth Credentials (required)
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Allowed email domain (defaults to @8thlight.com)
ALLOWED_EMAIL_DOMAIN=@8thlight.com

# Service base URLs (for OAuth redirects)
CONTROL_PLANE_BASE_URL=http://localhost:6001
SERVER_BASE_URL=http://localhost:5001
DASHBOARD_BASE_URL=http://localhost:8080

# Secret key for session encryption (required for production)
SECRET_KEY=your-secret-key-change-in-prod
```

### Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Configure OAuth consent screen:
   - User Type: Internal (for Workspace accounts)
   - Scopes: `openid`, `email`, `profile`
6. Create OAuth 2.0 Client ID:
   - Application type: Web application
   - Authorized redirect URIs:
     - `http://localhost:6001/auth/callback` (Control Plane)
     - `http://localhost:5001/auth/callback` (Tasks)
     - `http://localhost:8080/auth/callback` (Dashboard)
     - Add production URLs when deploying

## Authentication Flow

1. User accesses protected endpoint
2. If not authenticated, redirect to Google OAuth
3. User authenticates with Google account
4. System verifies email domain (`@8thlight.com`)
5. If authorized, create session and redirect to original URL
6. All authentication events are logged for auditing

## Audit Logging

All authentication events are logged with the following information:
- Timestamp
- Event type (login_initiated, login_success, login_denied_domain, logout, access_granted, etc.)
- User email
- IP address
- User agent
- Request path
- Success/failure status
- Error messages (if applicable)

Logs are written to:
- Console output (stdout)
- Service-specific log files:
  - `control_plane/logs/control_plane.log`
  - `tasks/logs/tasks.log`
  - Dashboard service logs (via uvicorn/gunicorn)

## Excluded Endpoints

The following endpoints are excluded from authentication:
- `/health` and `/api/health` - Health checks
- `/auth/*` - Authentication endpoints
- `/assets/*` - Static assets
- `/` - Root/UI pages (authentication happens on first API call)

## Security Features

- **Domain Restriction**: Only `@8thlight.com` emails are allowed
- **Secure Cookies**: Cookies are HTTP-only and SameSite=Lax
- **Session Management**: Secure session storage
- **HTTPS Ready**: Secure cookies enabled in production
- **Audit Trail**: All authentication events logged

## Testing

1. Start services:
   ```bash
   docker-compose up -d
   ```

2. Access any protected endpoint (e.g., `http://localhost:6001/api/agents`)

3. You should be redirected to Google OAuth login

4. After successful login with `@8thlight.com` account, you'll be redirected back

5. Check logs for authentication events:
   ```bash
   docker-compose logs -f control_plane | grep AUTH_AUDIT
   ```

## Troubleshooting

### "Google OAuth not configured" error
- Ensure `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set
- Verify credentials in Google Cloud Console

### "Access restricted to 8thlight.com domain" error
- User's email must end with `@8thlight.com`
- Check `ALLOWED_EMAIL_DOMAIN` environment variable

### Redirect URI mismatch
- Ensure redirect URIs in Google Cloud Console match your service URLs
- Check `CONTROL_PLANE_BASE_URL`, `SERVER_BASE_URL`, `DASHBOARD_BASE_URL`

### Session not persisting
- Verify `SECRET_KEY` is set (required for session encryption)
- Check cookie settings in browser developer tools

## Production Deployment

1. Update redirect URIs in Google Cloud Console to production URLs
2. Set `ENVIRONMENT=production` to enable secure cookies
3. Use strong `SECRET_KEY` for session encryption
4. Ensure HTTPS is enabled (required for secure cookies)
5. Review audit logs regularly for security monitoring

## Implementation Details

### Control Plane (Flask)
- Uses Flask sessions
- `@app.before_request` middleware for route protection
- Auth module: `control_plane/utils/auth.py`

### Tasks Service (Flask)
- Uses Flask sessions
- `@app.before_request` middleware for route protection
- Auth module: `tasks/utils/auth.py`
- Google Drive OAuth endpoints excluded (separate flow)

### Dashboard Service (FastAPI)
- Uses Starlette SessionMiddleware
- Custom ASGI middleware for route protection
- Auth module: `dashboard-service/utils/auth.py`

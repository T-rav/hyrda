# SSL Certificate Setup Guide

This guide explains how to set up and trust self-signed SSL certificates for local development.

## Overview

InsightMesh uses HTTPS for all inter-service communication with self-signed certificates. Certificates are automatically trusted in Docker containers, but require a one-time setup for local macOS development.

## Architecture

### Services with HTTPS
- **Qdrant** (vector database) - Port 6333
- **control-plane** - Port 6001
- **agent-service** - Port 8000
- **tasks** - Port 5001

### Certificate Files
All certificates are stored in `.ssl/`:
```
.ssl/
├── agent-service-cert.pem     # Agent service certificate
├── agent-service-key.pem      # Agent service private key
├── control-plane-cert.pem     # Control plane certificate
├── control-plane-key.pem      # Control plane private key
├── qdrant-cert.pem            # Qdrant certificate
├── qdrant-key.pem             # Qdrant private key
├── rag-service-cert.pem       # RAG service certificate
├── rag-service-key.pem        # RAG service private key
├── tasks-cert.pem             # Tasks service certificate
└── tasks-key.pem              # Tasks service private key
```

## Docker Container Setup (Automatic)

All Docker containers automatically trust certificates via system CA store:

1. Certificates are copied to `/usr/local/share/ca-certificates/`
2. `update-ca-certificates` runs during build
3. All Python clients use proper SSL validation (no `verify=False`)

This happens automatically during Docker build - no action required!

## Local macOS Setup (One-Time)

For local development (running tests, CLI tools), trust certificates on your machine:

### Automatic Method (Recommended)

Run the automated setup script:

```bash
./scripts/trust-local-certs.sh
```

This will:
- Find all certificates in `.ssl/`
- Add them to macOS System Keychain
- Skip already-trusted certificates
- Provide detailed feedback

You'll be prompted for your password (sudo required).

### Manual Method

If you prefer to add certificates manually:

```bash
# Add each certificate to System Keychain
for cert in .ssl/*-cert.pem; do
    sudo security add-trusted-cert -d -r trustRoot \
        -k /Library/Keychains/System.keychain "$cert"
done
```

### Verification

Verify certificates are trusted:

```bash
# Check System Keychain for InsightMesh certificates
security find-certificate -a /Library/Keychains/System.keychain | grep -A5 InsightMesh

# Or use Keychain Access.app
open "/Applications/Utilities/Keychain Access.app"
# Navigate to System keychain → Certificates
```

## Removing Certificates

When you're done with local development or want to clean up:

```bash
./scripts/remove-local-certs.sh
```

This removes all InsightMesh certificates from your System Keychain.

## Integration Tests

After trusting certificates locally, integration tests will work without SSL errors:

```bash
# Run infrastructure tests with proper SSL validation
export VECTOR_API_KEY="your-qdrant-api-key"
venv/bin/pytest bot/tests/test_integration_qdrant.py -v

# All Qdrant HTTPS connections will validate properly
```

## Troubleshooting

### Certificate Already Exists Error

If you see "certificate already exists" errors:

```bash
# Remove existing certificate first
sudo security delete-certificate -c "qdrant-cert.pem" \
    /Library/Keychains/System.keychain

# Then re-run trust script
./scripts/trust-local-certs.sh
```

### SSL Verification Failures

If you see SSL errors like "certificate verify failed":

1. **Check certificates are trusted**: Run verification steps above
2. **Regenerate certificates**: Run `./scripts/setup-ssl.sh`
3. **Re-trust certificates**: Run `./scripts/trust-local-certs.sh`

### Services Not Using HTTPS

All services should use HTTPS. Check configuration:

```bash
# Qdrant should use https://
grep -r "https://.*:6333" bot/ rag-service/ agent-service/ tasks/

# No verify=False should exist
grep -r "verify=False" bot/ rag-service/ agent-service/ tasks/
```

## Production Deployment

In production:

1. **Use proper CA-signed certificates** (Let's Encrypt, AWS ACM, etc.)
2. **Update docker-compose.yml** to mount production certificates
3. **Remove self-signed certs** from `.ssl/` and use production certs

The Docker container setup will work the same way - just mount your production certificates instead of self-signed ones.

## Security Notes

### Self-Signed Certificates
- ✅ **Development**: Convenient, no external dependencies
- ❌ **Production**: Not recommended, use proper CA-signed certificates

### Certificate Validation
- ✅ **Always enabled**: All services validate SSL certificates
- ❌ **Never bypassed**: No `verify=False` in production code
- ✅ **System CA store**: Certificates trusted via OS-level mechanism

### Private Keys
- ⚠️ **Never commit to version control**: `.ssl/` is in `.gitignore`
- ⚠️ **Regenerate for each environment**: Development, staging, production
- ⚠️ **Protect access**: Private keys should be readable only by services

## Reference

### Certificate Generation

Certificates are generated by `./scripts/setup-ssl.sh`:

```bash
# Generate all service certificates
./scripts/setup-ssl.sh

# This creates certificates valid for 365 days
# Certificates include localhost, service names, and IP addresses
```

### Python SSL Configuration

All Qdrant clients use proper SSL validation:

```python
# bot/services/vector_stores/qdrant_store.py
self.client = QdrantClient(
    url=f"https://{self.host}:{self.port}",
    api_key=self.api_key,
    timeout=60,
    # verify=True by default - uses system CA store
)
```

### Docker SSL Configuration

All Dockerfiles install certificates:

```dockerfile
# Trust all self-signed certificates for inter-service communication
COPY .ssl/*-cert.pem /usr/local/share/ca-certificates/
RUN update-ca-certificates
```

---

**Questions?** See the main [README.md](../README.md) or check infrastructure tests in `bot/tests/test_integration_*.py`.

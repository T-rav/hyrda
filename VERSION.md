# InsightMesh Versioning & Release Guide

This document describes the versioning system and release workflow for InsightMesh.

## Version Management

### Single Source of Truth

The `.version` file in the project root is the single source of truth for the application version:

```
1.1.0
```

This version is:
- Used to tag Docker images
- Embedded in container labels (OCI standard)
- Available in containers via `APP_VERSION` environment variable
- Referenced by docker-compose.prod.yml

### Makefile Commands

```bash
# Show current version and image information
make version

# Bump version (patch, minor, or major)
make version-bump

# Build images with version tags
make docker-build

# Tag images for registry
make docker-tag REGISTRY=ghcr.io/myorg

# Push to registry
make docker-push REGISTRY=ghcr.io/myorg

# Full release workflow (bump + build + push)
make release REGISTRY=ghcr.io/myorg
```

### Release Script

For automated releases, use the release script:

```bash
# Patch release and push to GHCR
./scripts/release.sh patch ghcr.io/myorg

# Minor release
./scripts/release.sh minor ghcr.io/myorg

# Major release
./scripts/release.sh major ghcr.io/myorg

# Build current version without bump
./scripts/release.sh none ghcr.io/myorg
```

## Docker Image Tags

Each release produces the following tags:

| Tag | Example | Description |
|-----|---------|-------------|
| Version | `ghcr.io/myorg/insightmesh-bot:1.1.0` | Specific version |
| Latest | `ghcr.io/myorg/insightmesh-bot:latest` | Always points to latest release |
| SHA | `ghcr.io/myorg/insightmesh-bot:sha-abc1234` | Git commit SHA (optional) |

## Production Deployment

### 1. Configure Environment

Set in `.env` file:

```env
REGISTRY=ghcr.io/yourorg
VERSION=1.1.0
```

### 2. Build and Push Images

```bash
make release REGISTRY=ghcr.io/yourorg
```

### 3. Deploy to Production

Signal Room should use `docker-compose.prod.yml`:

```bash
# Pull and deploy specific version
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

The production compose file:
- Uses pre-built images from the registry
- References specific version tags
- Includes volume mounts for custom code (custom_agents, etc.)
- Configures health checks and restart policies

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Release
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push
        run: |
          VERSION=${GITHUB_REF#refs/tags/v}
          echo "$VERSION" > .version
          make release REGISTRY=ghcr.io/${{ github.repository_owner }}
```

## Image Labels

All images include OCI-compliant labels:

```dockerfile
LABEL org.opencontainers.image.title="InsightMesh Bot"
LABEL org.opencontainers.image.version="1.1.0"
LABEL org.opencontainers.image.revision="abc1234"
LABEL org.opencontainers.image.created="2026-02-10T15:00:00Z"
```

View labels:

```bash
docker inspect ghcr.io/myorg/insightmesh-bot:1.1.0 | jq '.[0].Config.Labels'
```

## Version Checking

Inside containers, the version is available:

```bash
# Environment variable
echo $APP_VERSION

# Docker labels
docker inspect <container> | jq '.[0].Config.Labels["org.opencontainers.image.version"]'
```

## Rollback Procedure

To rollback to a previous version:

```bash
# Update .env to previous version
VERSION=1.0.0

# Pull and deploy
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Best Practices

1. **Always bump version for releases** - Don't overwrite existing tags
2. **Tag Git commits** - Use `v1.1.0` format for Git tags
3. **Test locally before pushing** - Run `make docker-build` first
4. **Use immutable tags** - Pin to specific versions in production
5. **Keep latest tag updated** - Always push latest alongside version

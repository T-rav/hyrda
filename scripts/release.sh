#!/bin/bash
# Release script for InsightMesh
# Usage: ./scripts/release.sh [patch|minor|major] [registry]
# Example: ./scripts/release.sh patch ghcr.io/myorg

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Change to project root
cd "${PROJECT_ROOT}"

# Default values
BUMP_TYPE="${1:-patch}"
REGISTRY="${2:-}"

# Show help
if [ "$BUMP_TYPE" = "--help" ] || [ "$BUMP_TYPE" = "-h" ]; then
    echo -e "${BLUE}InsightMesh Release Script${RESET}"
    echo ""
    echo "Usage: $0 [BUMP_TYPE] [REGISTRY]"
    echo ""
    echo "Arguments:"
    echo "  BUMP_TYPE    Version bump type: patch, minor, major (default: patch)"
    echo "  REGISTRY     Container registry (e.g., ghcr.io/myorg, docker.io/user)"
    echo ""
    echo "Examples:"
    echo "  $0 patch ghcr.io/myorg          # Patch bump and push to GHCR"
    echo "  $0 minor                        # Minor bump, local build only"
    echo "  $0 major docker.io/myuser       # Major bump and push to Docker Hub"
    echo ""
    echo "Environment Variables:"
    echo "  REGISTRY_TOKEN    Auth token for registry login (optional)"
    exit 0
fi

# Validate bump type
if [[ ! "$BUMP_TYPE" =~ ^(patch|minor|major|none)$ ]]; then
    echo -e "${RED}Error: Invalid bump type '$BUMP_TYPE'${RESET}"
    echo "Valid options: patch, minor, major, none"
    exit 1
fi

# Get current version
CURRENT_VERSION=$(cat .version)
echo -e "${BLUE}Current version: ${GREEN}${CURRENT_VERSION}${RESET}"

# Calculate new version
if [ "$BUMP_TYPE" != "none" ]; then
    MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
    MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)
    PATCH=$(echo "$CURRENT_VERSION" | cut -d. -f3)

    case "$BUMP_TYPE" in
        major)
            MAJOR=$((MAJOR + 1))
            MINOR=0
            PATCH=0
            ;;
        minor)
            MINOR=$((MINOR + 1))
            PATCH=0
            ;;
        patch)
            PATCH=$((PATCH + 1))
            ;;
    esac

    NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
    echo -e "${BLUE}New version: ${GREEN}${NEW_VERSION}${RESET}"

    # Confirm
    read -p "Continue with release? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Release cancelled${RESET}"
        exit 0
    fi

    # Update version file
    echo "$NEW_VERSION" > .version
    echo -e "${GREEN}✅ Version bumped to ${NEW_VERSION}${RESET}"

    # Git commit
    git add .version
    git commit -m "chore(release): bump version to ${NEW_VERSION}"
    git tag "v${NEW_VERSION}"
    echo -e "${GREEN}✅ Git tag created: v${NEW_VERSION}${RESET}"
else
    NEW_VERSION=$CURRENT_VERSION
fi

# Build images
echo -e "${BLUE}🔨 Building Docker images...${RESET}"
make docker-build

# Tag and push if registry provided
if [ -n "$REGISTRY" ]; then
    echo -e "${BLUE}🏷️  Tagging images for ${REGISTRY}...${RESET}"
    make docker-tag REGISTRY="$REGISTRY"

    # Login to registry if token provided
    if [ -n "$REGISTRY_TOKEN" ]; then
        echo -e "${BLUE}🔐 Logging into registry...${RESET}"
        if [[ "$REGISTRY" == ghcr.io* ]]; then
            echo "$REGISTRY_TOKEN" | docker login ghcr.io -u "${REGISTRY_USER:-$USER}" --password-stdin
        elif [[ "$REGISTRY" == docker.io* ]]; then
            echo "$REGISTRY_TOKEN" | docker login docker.io -u "${REGISTRY_USER}" --password-stdin
        fi
    fi

    echo -e "${BLUE}📤 Pushing images to ${REGISTRY}...${RESET}"
    make docker-push REGISTRY="$REGISTRY"

    echo -e "${GREEN}✅ Images pushed to ${REGISTRY}${RESET}"
fi

# Summary
echo ""
echo -e "${GREEN}🎉 Release ${NEW_VERSION} complete!${RESET}"
echo ""
echo -e "${BLUE}Summary:${RESET}"
echo "  Version: ${GREEN}${NEW_VERSION}${RESET}"
if [ -n "$REGISTRY" ]; then
    echo "  Images:  ${YELLOW}${REGISTRY}/insightmesh-*:${NEW_VERSION}${RESET}"
fi
echo ""
echo -e "${BLUE}Next steps:${RESET}"
if [ "$BUMP_TYPE" != "none" ]; then
    echo "  1. git push && git push --tags"
fi
if [ -n "$REGISTRY" ]; then
    echo "  2. Update docker-compose.prod.yml with version ${NEW_VERSION}"
    echo "  3. Deploy: docker compose -f docker-compose.prod.yml up -d"
fi

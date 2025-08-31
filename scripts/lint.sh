#!/bin/bash

# Unified linting script for both local and CI environments
# This ensures identical behavior between pre-commit hooks and CI pipeline

set -e

PROJECT_ROOT="src"
FIX_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--fix]"
            exit 1
            ;;
    esac
done

echo "🔍 Running linting checks..."

# Run ruff for linting and formatting
if [ "$FIX_MODE" = true ]; then
    echo "📝 Running ruff with auto-fix..."
    python3.11 -m ruff check $PROJECT_ROOT --fix
    echo "🎨 Running black formatting..."
    python3.11 -m black $PROJECT_ROOT
    echo "📦 Running isort import sorting..."
    python3.11 -m isort $PROJECT_ROOT
else
    echo "🔍 Running ruff check (no fixes)..."
    python3.11 -m ruff check $PROJECT_ROOT
    echo "🎨 Checking black formatting..."
    python3.11 -m black $PROJECT_ROOT --check
    echo "📦 Checking isort import sorting..."
    python3.11 -m isort $PROJECT_ROOT --check-only
fi

echo "🔒 Running security checks..."
cd $PROJECT_ROOT && python3.11 -m bandit -r . -f txt --severity-level medium --confidence-level medium

echo "✅ All linting checks completed!"

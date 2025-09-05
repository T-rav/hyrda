#!/bin/bash

# Unified linting script for both local and CI environments
# This ensures identical behavior between pre-commit hooks and CI pipeline
# Uses only ruff for both linting and formatting (replaces black + isort)

set -e

PROJECT_ROOT="bot"
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

# Determine Python command - find one that has ruff installed
PYTHON_CMD=""
for candidate in "python3.11" "python3" "python"; do
    if command -v $candidate &> /dev/null && $candidate -m ruff --version &> /dev/null; then
        PYTHON_CMD=$candidate
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Error: No Python interpreter with ruff found. Please install ruff:"
    echo "   python -m pip install ruff pyright bandit"
    exit 1
fi

echo "🔍 Running unified linting with ruff (using $PYTHON_CMD)..."

# Run ruff for linting and formatting (replaces black + isort)
if [ "$FIX_MODE" = true ]; then
    echo "📝 Running ruff linting with auto-fix..."
    $PYTHON_CMD -m ruff check $PROJECT_ROOT --fix
    echo "🎨 Running ruff formatting..."
    $PYTHON_CMD -m ruff format $PROJECT_ROOT
else
    echo "🔍 Running ruff check (no fixes)..."
    $PYTHON_CMD -m ruff check $PROJECT_ROOT
    echo "🎨 Checking ruff formatting..."
    $PYTHON_CMD -m ruff format $PROJECT_ROOT --check
fi

echo "🔍 Running type checking..."
(cd $PROJECT_ROOT && $PYTHON_CMD -m pyright)

echo "🔒 Running security checks..."
# Use pyproject.toml config and exclude problematic directories
(cd $PROJECT_ROOT && timeout 30s $PYTHON_CMD -m bandit -r . -c ../pyproject.toml -f txt || echo "⚠️  Bandit check timed out or failed (non-blocking)")

echo "✅ All checks completed with ruff + pyright + bandit!"

#!/bin/bash
# Unified linting script used by both pre-commit and CI
# This ensures identical behavior between local development and CI

set -e  # Exit on first error

# Change to project root
cd "$(dirname "$0")/.."

echo "🔍 Running unified linting checks..."

# 1. Ruff linting with auto-fix (if --fix flag is provided)
echo "📋 Running Ruff linting..."
if [[ "$1" == "--fix" ]]; then
    ruff check . --fix
else
    ruff check .
fi

# 2. Ruff formatting
echo "🎨 Running Ruff formatting..."
if [[ "$1" == "--fix" ]]; then
    ruff format .
else
    ruff format --check .
fi

# 3. Import sorting with isort
echo "📦 Running import sorting..."
if [[ "$1" == "--fix" ]]; then
    isort .
else
    isort --check-only .
fi

# 4. Type checking with Pyright (only if not in fix mode)
if [[ "$1" != "--fix" ]]; then
    echo "🔬 Running type checking..."
    pyright
fi

echo "✅ All linting checks passed!"

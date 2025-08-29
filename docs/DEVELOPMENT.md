# Development Environment Setup

This document explains the unified development environment that ensures identical behavior between local development and CI.

## Unified Linting Approach

Both pre-commit hooks and CI use the **same script** (`./scripts/lint.sh`) and **exact tool versions** to prevent discrepancies.

### Key Components

1. **Unified Script**: `./scripts/lint.sh`
   - Single source of truth for all linting operations
   - Used by both pre-commit hooks and CI
   - Supports `--fix` mode for local development

2. **Exact Versions**: `requirements-dev.txt`
   - Pins exact tool versions for reproducibility
   - Used by both local development and CI
   - Eliminates version-related inconsistencies

3. **Common Configuration**: `pyproject.toml`
   - Single configuration file for all tools
   - Shared between local and CI environments

## Setup Instructions

### Initial Setup
```bash
# Install exact development tool versions
make setup-dev

# This will:
# - Install pinned tool versions from requirements-dev.txt
# - Install pre-commit hooks
# - Set up test environment
```

### Daily Development
```bash
# Auto-fix linting issues
make lint

# Check without fixing (same as CI)
make lint-check

# Run full quality checks
make quality
```

### Tool Versions
All environments use these exact versions:
- **Ruff**: 0.8.4 (linting + formatting)
- **isort**: 5.13.2 (import sorting)  
- **Pyright**: 1.1.390 (type checking)
- **Bandit**: 1.8.0 (security scanning)

## How It Works

### Local Development (Pre-commit)
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: unified-lint-check
      entry: ./scripts/lint.sh  # Same script as CI!
```

### CI Pipeline
```yaml
# .github/workflows/test.yml  
- name: Run unified linting and type checking
  run: |
    ./scripts/lint.sh  # Same script as local!
```

### The Unified Script
```bash
# scripts/lint.sh
ruff check .                 # Linting
ruff format --check .        # Formatting  
isort --check-only .         # Import sorting
pyright                      # Type checking
```

## Benefits

1. **Identical Behavior**: Same script = same results everywhere
2. **Version Consistency**: Pinned versions eliminate surprises
3. **Faster Debugging**: Issues caught locally match CI exactly
4. **Single Maintenance**: One script to update, not multiple configs
5. **Tool Standardization**: Ruff for both linting and formatting

## Troubleshooting

### Pre-commit vs CI Mismatch
This should no longer happen! Both use the same script and versions.

If you see differences:
1. Check your tool versions: `pip list | grep -E "ruff|isort|pyright"`
2. Reinstall dev tools: `pip install -r requirements-dev.txt`
3. Re-run: `./scripts/lint.sh`

### Legacy Black References
We're transitioning from Black to Ruff format. If you see Black errors:
- Update your commands to use `make lint` instead of `black .`
- The Makefile now uses Ruff format internally

## Migration Notes

For existing contributors:
1. Run `make setup-dev` to get the new unified environment
2. Use `make lint` instead of individual tool commands
3. Pre-commit hooks now run the unified script automatically

This ensures everyone has the same development experience! 🎉

# Pre-commit Hooks Setup

This project uses pre-commit hooks to automatically check and format code before commits.

## Quick Setup

```bash
# Install all development dependencies and set up pre-commit hooks
make setup-dev
```

This will:
1. Install Python dependencies (including pre-commit)
2. Install and configure pre-commit hooks
3. Copy test environment file

## Manual Setup

If you prefer to set up manually:

```bash
# Install pre-commit
pip install pre-commit

# Install the hooks
pre-commit install

# Test the hooks (optional)
pre-commit run --all-files
```

## What the Hooks Do

When you commit, the following will run automatically:

### Code Quality & Formatting
- **Ruff**: Fast linting with auto-fix for Python code
- **Ruff Format**: Fast formatting (alternative to Black)
- **Black**: Code formatting (backup/compatibility)
- **isort**: Import statement sorting

### Type Checking
- **MyPy**: Static type checking (excludes tests)

### General Cleanup
- Remove trailing whitespace
- Ensure files end with newlines
- Check for merge conflicts
- Validate YAML, JSON, TOML syntax
- Check for large files (>1MB)
- Fix line endings (LF)

### Security
- **Bandit**: Security vulnerability scanning

## Usage

### Automatic (Recommended)
Hooks run automatically on every `git commit`. If they find issues:

1. **Auto-fixable issues**: Fixed automatically, commit stops
   - Re-stage the fixed files: `git add .`
   - Commit again: `git commit -m "Your message"`

2. **Manual fixes needed**: Commit stops, you fix manually
   - Fix the reported issues
   - Stage and commit again

### Manual
```bash
# Run all hooks on all files
make pre-commit
# OR
pre-commit run --all-files

# Run specific hook
pre-commit run ruff
pre-commit run black
pre-commit run mypy

# Run security scan
make security
```

### Skip Hooks (Emergency Only)
```bash
# Skip all hooks (not recommended)
git commit --no-verify -m "Emergency fix"

# Skip specific hook
SKIP=mypy git commit -m "Skip type checking"
```

## Configuration

### Pre-commit Config
- File: `.pre-commit-config.yaml`
- Controls which hooks run and their settings

### Tool Configs
- **Ruff/Black/isort/MyPy**: `pyproject.toml`
- **Bandit**: `pyproject.toml` 
- **Coverage**: `pyproject.toml`

### Updating Hooks
```bash
# Update to latest versions
pre-commit autoupdate

# Update specific hook
pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit
```

## Troubleshooting

### Hook Installation Issues
```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install

# Clean cache
pre-commit clean
```

### MyPy Errors
MyPy runs with `--ignore-missing-imports` but may still complain:
```bash
# Install missing type stubs
pip install types-redis types-requests
```

### Performance
Hooks only run on changed files by default. For full project scans:
```bash
# Run on all files (slower)
pre-commit run --all-files
```

## IDE Integration

Most IDEs can be configured to run these tools on save:
- **VS Code**: Python extension + Ruff extension
- **PyCharm**: Configure external tools for ruff, black, isort
- **Vim/Neovim**: Use ALE, coc-pyright, or similar plugins

This ensures code is formatted before pre-commit hooks even run.
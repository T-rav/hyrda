# Development Notes

Quick reference for development tasks not covered in CLAUDE.md.

## Version Management

The bot uses **dynamic versioning** from `pyproject.toml`:

### Updating Version
1. **Edit `bot/pyproject.toml`** (line 7):
   ```toml
   version = "1.2.5"  # ← Change this
   ```

2. **Restart the bot** - version automatically appears in:
   - Health dashboard at `http://localhost:8080/ui`
   - Footer of the dashboard
   - `/api/health` endpoint response

### Benefits
- ✅ **Single source of truth** - no hardcoded versions
- ✅ **Automatic propagation** - appears everywhere instantly  
- ✅ **Standard Python packaging** - follows PEP 440
- ✅ **Health monitoring integration** - visible in dashboard

## Quick Setup

```bash
make setup-dev  # Install dependencies + pre-commit hooks
```

For development workflows, see `CLAUDE.md`.

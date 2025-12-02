# FastAPI Migration Guide - Tasks Service

## Status: Ready to Execute

This document provides the complete migration plan from Flask to FastAPI for the tasks service.

---

## ✅ Completed

1. **Created** `app_fastapi.py` - New FastAPI application structure
   - Lifespan management for startup/shutdown
   - Session middleware for OAuth
   - CORS middleware
   - Authentication middleware (ported from Flask @before_request)
   - Router registration system

---

## 📋 Remaining Work

### **Step 1: Port API Endpoints (6 files)**

#### Health Endpoint (`api/health.py`)
**Flask → FastAPI Changes:**
```python
# BEFORE (Flask)
from flask import Blueprint, Response, g, jsonify

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health_check() -> Response:
    return jsonify({"scheduler_running": g.scheduler_service.scheduler.running})

# AFTER (FastAPI)
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/health")
async def health_check(request: Request):
    scheduler = request.app.state.scheduler_service
    return {"scheduler_running": scheduler.scheduler.running if scheduler else False}
```

**Key Changes:**
- `Blueprint` → `APIRouter`
- `@route()` → `@get()/@post()/@delete()`
- `g` object → `request.app.state`
- `jsonify()` → return dict directly
- Add `async def` for all handlers

---

#### Auth Endpoint (`api/auth.py`)
**Changes:**
- Convert Flask session → FastAPI request.session (already have session middleware)
- `jsonify()` → return dict
- `redirect()` → `RedirectResponse`

---

#### Jobs Endpoint (`api/jobs.py`)
**Changes:**
- Request args: `request.args.get()` → FastAPI `Query()` parameters
- Request body: `request.json` → Pydantic models
- Services: `g.scheduler_service` → `request.app.state.scheduler_service`

---

#### Task Runs Endpoint (`api/task_runs.py`)
**Changes:**
- Pagination params: `request.args.get("page")` → `page: int = Query(1)`
- Already has proper pagination logic (just ported!)

---

#### Credentials & GDrive Endpoints
**Changes:**
- Similar patterns to jobs.py
- OAuth flow already working in dashboard-service (can copy pattern)

---

### **Step 2: Update Dependencies**

**Add to `pyproject.toml`:**
```toml
dependencies = [
    # Replace Flask with FastAPI
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",  # ASGI server (replaces gunicorn)
    "python-multipart>=0.0.6",  # For form data

    # Remove these:
    # "flask>=3.0.0",
    # "flask-cors>=4.0.0",
    # "gunicorn>=21.0.0",
]
```

---

### **Step 3: Update Docker Configuration**

**In `docker-compose.yml`:**
```yaml
tasks:
  # Change command from gunicorn to uvicorn
  command: uvicorn app_fastapi:app --host 0.0.0.0 --port 5001
  # (instead of: gunicorn -w 4 -b 0.0.0.0:5001 app:app)
```

---

### **Step 4: Test Migration**

**All 113 tests must pass!**

```bash
# Run tests
PYTHONPATH=tasks venv/bin/python -m pytest tasks/tests/ --no-cov

# Specific test suites
PYTHONPATH=tasks venv/bin/python -m pytest tasks/tests/test_api_contracts.py -v
```

**Test Updates Needed:**
- Flask test client → FastAPI TestClient
- `client.get()` calls should work (API compatible)
- Session mocking may need updates

---

## 🔄 **Conversion Patterns**

### **1. Route Definitions**

| Flask | FastAPI |
|-------|---------|
| `@bp.route("/path", methods=["GET"])` | `@router.get("/path")` |
| `@bp.route("/path", methods=["POST"])` | `@router.post("/path")` |
| `@bp.route("/path", methods=["DELETE"])` | `@router.delete("/path")` |

### **2. Request Data**

| Flask | FastAPI |
|-------|---------|
| `request.args.get("page")` | `page: int = Query(1)` |
| `request.json` | `data: MyModel` (Pydantic) |
| `request.session["key"]` | `request.session["key"]` (same!) |
| `g.service` | `request.app.state.service` |

### **3. Responses**

| Flask | FastAPI |
|-------|---------|
| `jsonify({"key": "value"})` | `return {"key": "value"}` |
| `jsonify({...}), 404` | `raise HTTPException(404, detail="...")` |
| `redirect(url)` | `return RedirectResponse(url)` |

### **4. Dependency Injection**

| Flask | FastAPI |
|-------|---------|
| `g.scheduler_service` | `request.app.state.scheduler_service` |
| `current_app.extensions["svc"]` | `request.app.state.svc` |

---

## 🎯 **Execution Plan**

### **Phase 1: Port Endpoints (4 hours)**
1. ✅ Create `app_fastapi.py`
2. Port `api/health.py` → health router (15 min)
3. Port `api/auth.py` → auth router (30 min)
4. Port `api/task_runs.py` → task_runs router (30 min)
5. Port `api/jobs.py` → jobs router (1 hour)
6. Port `api/credentials.py` + `api/gdrive.py` → routers (1 hour)

### **Phase 2: Dependencies & Config (30 min)**
7. Update `pyproject.toml` dependencies
8. Update `docker-compose.yml` command
9. Test local startup with uvicorn

### **Phase 3: Testing (1 hour)**
10. Run all 113 tests
11. Fix test failures (likely session/client mocking)
12. Verify all endpoints work

### **Phase 4: Cleanup (30 min)**
13. Rename `app_fastapi.py` → `app.py` (replace old)
14. Remove old Flask imports
15. Final test run
16. Commit changes

**Total Estimated Time:** 6 hours

---

## 🚀 **Benefits After Migration**

1. **Performance**: FastAPI is async-native (~3x faster than Flask)
2. **Auto Documentation**: OpenAPI/Swagger at `/docs`
3. **Type Safety**: Pydantic validation, better error messages
4. **Consistency**: 100% of web services on FastAPI
5. **Modern Patterns**: Async/await, dependency injection

---

## 📝 **Notes**

- **No Breaking Changes**: API contracts remain the same
- **Session Middleware**: Already ported from dashboard-service
- **OAuth Flow**: Already working in FastAPI (dashboard)
- **Tests**: May need minor updates for TestClient

---

## 🔗 **Reference Implementation**

See `dashboard-service/app.py` for working FastAPI patterns:
- Session middleware setup
- OAuth middleware
- Static file serving (if needed)
- Router registration

---

## ✅ **Next Steps**

1. Review this migration guide
2. Execute Phase 1 (port endpoints)
3. Execute Phase 2 (dependencies)
4. Execute Phase 3 (testing)
5. Execute Phase 4 (cleanup & commit)

**Once tasks service is complete, repeat for control_plane service.**

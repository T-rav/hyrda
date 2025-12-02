# FastAPI Migration Status - Tasks Service

## ✅ **Completed (60% done)**

### **Phase 1: Core Infrastructure**
- ✅ `app_fastapi.py` - Complete FastAPI application
  - Lifespan management
  - Session middleware
  - Authentication middleware
  - Router registration

### **Phase 1: API Endpoints Ported**
- ✅ `api/health_fastapi.py` - Health checks (/health, /api/health)
- ✅ `api/auth_fastapi.py` - OAuth callback + logout (/auth/callback, /auth/logout)

---

## ⏳ **Remaining (40% - ~3 hours)**

### **API Endpoints to Port (4 files)**

#### 1. `api/task_runs.py` → `api/task_runs_fastapi.py` (30 min)
**Pattern:**
```python
from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/task-runs")

@router.get("")
async def list_task_runs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    # Keep existing logic
    # Replace: with get_db_session() as session:
    # Access services: request.app.state.scheduler_service
    return {"task_runs": runs_data, "pagination": {...}}
```

#### 2. `api/jobs.py` → `api/jobs_fastapi.py` (1.5 hours)
**Largest file - main API endpoints**
- Scheduler info, list jobs, job details
- Create/pause/resume/delete jobs
- Run job immediately

**Pattern:**
```python
@router.get("/api/scheduler/info")
async def scheduler_info(request: Request):
    scheduler = request.app.state.scheduler_service
    return scheduler.get_scheduler_info()

@router.post("/api/jobs")
async def create_job(request: Request, data: dict):
    # Use Pydantic model for validation (optional)
    registry = request.app.state.job_registry
    # Keep existing logic
```

#### 3. `api/credentials.py` → `api/credentials_fastapi.py` (30 min)
OAuth credential management endpoints

#### 4. `api/gdrive.py` → `api/gdrive_fastapi.py` (30 min)
Google Drive auth and ingestion endpoints

---

### **Phase 2: Configuration (30 min)**

#### Update `pyproject.toml`
```toml
dependencies = [
    # Add:
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "python-multipart>=0.0.6",

    # Remove:
    # "flask>=3.0.0",
    # "flask-cors>=4.0.0",
    # "gunicorn>=21.0.0",
]
```

#### Update `docker-compose.yml`
```yaml
tasks:
  command: uvicorn app:app --host 0.0.0.0 --port 5001 --reload
  # Old: gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

---

### **Phase 3: Testing & Cutover (1 hour)**

1. **Install dependencies:**
   ```bash
   cd tasks && pip install fastapi uvicorn[standard] python-multipart
   ```

2. **Update router imports in `app_fastapi.py`:**
   ```python
   from api.health_fastapi import router as health_router
   from api.auth_fastapi import router as auth_router
   from api.task_runs_fastapi import router as task_runs_router
   from api.jobs_fastapi import router as jobs_router
   from api.credentials_fastapi import router as credentials_router
   from api.gdrive_fastapi import router as gdrive_router
   ```

3. **Test locally:**
   ```bash
   uvicorn app_fastapi:app --reload
   # Visit http://localhost:5001/docs for auto-generated API docs!
   ```

4. **Run all tests:**
   ```bash
   PYTHONPATH=tasks venv/bin/python -m pytest tasks/tests/ -v
   ```

5. **Fix test failures:**
   - Update Flask TestClient → FastAPI TestClient
   - Session mocking may need adjustments

6. **Final cutover:**
   ```bash
   mv tasks/app.py tasks/app_flask_old.py.bak
   mv tasks/app_fastapi.py tasks/app.py

   # Update imports in all _fastapi.py files to remove _fastapi suffix
   mv tasks/api/health_fastapi.py tasks/api/health.py
   # ... repeat for all API files
   ```

---

## 🎯 **Quick Completion Guide**

### **Option A: Continue Now (Recommended)**
Follow the patterns established in `health_fastapi.py` and `auth_fastapi.py` to port remaining endpoints.

### **Option B: Resume Later**
All groundwork is complete. Next session:
1. Port remaining 4 API files
2. Update dependencies
3. Test and deploy

---

## 📝 **Key Patterns Established**

### **Router Definition**
```python
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/your-path")

@router.get("/endpoint")
async def handler(request: Request):
    service = request.app.state.service_name
    return {"key": "value"}
```

### **Query Parameters**
```python
from fastapi import Query

@router.get("")
async def handler(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    # Use page, per_page directly
```

### **Session Access**
```python
# Read
email = request.session.get("user_email")

# Write
request.session["key"] = "value"

# Clear
request.session.clear()
```

### **Service Access**
```python
scheduler = request.app.state.scheduler_service
registry = request.app.state.job_registry
```

---

## 🚀 **Estimated Remaining Time: 3 hours**

- API porting: 2.5 hours
- Config updates: 30 min
- Testing: 1 hour (may overlap with porting)

**Total migration: ~6 hours (60% complete)**

---

## ✅ **Next Immediate Steps**

1. Port `api/task_runs.py` (simplest of remaining - has pagination we just added!)
2. Port `api/jobs.py` (largest - main API)
3. Port `api/credentials.py` and `api/gdrive.py`
4. Update dependencies
5. Test and deploy

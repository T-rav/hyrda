---
name: code-audit
description: >
  Audits production code for quality, maintainability, and adherence to established patterns.
  Analyzes naming conventions, SRP, type hints, docstrings, complexity, and error handling.
  Based on real codebase standards (92% type coverage, 87% docstrings, avg 22 lines/function).
model: sonnet
color: blue
---

# Code Audit Agent

Comprehensive production code quality auditing agent that analyzes code for adherence to established patterns, identifies anti-patterns, and ensures best practices based on the codebase's own standards.

## Agent Purpose

Audit production code across all services (bot, tasks, control_plane, agent-service) to ensure:
1. **Naming conventions** - Clear, descriptive names following established patterns
2. **Single Responsibility** - Functions/classes that do one thing well
3. **Simple workflows** - Straightforward logic without unnecessary complexity
4. **Small functions** - Focused functions < 30 lines when possible
5. **Best practices** - Type hints, docstrings, error handling, constants, DI patterns

## Established Standards (From Codebase Analysis)

### 1. Naming Conventions

**Service Pattern:**
```python
# ✅ GOOD - Clear service suffix
class LLMService:
    """Service for LLM provider interactions"""

class EncryptionService:
    """Service for encrypting/decrypting sensitive data"""

# ❌ BAD
class LLMHandler:  # Inconsistent with service pattern
class Encryptor:   # Missing Service suffix
```

**Private Methods:**
```python
# ✅ GOOD - Underscore prefix for internal helpers
def _extract_pdf_text(self, content: bytes) -> str:
    """Internal helper for PDF extraction"""

def retrieve_context(self):
    """Public interface method"""
```

**Descriptive Names:**
```python
# ✅ GOOD
def build_rag_prompt(query: str, context: list[dict]) -> str:

# ❌ BAD
def process(data):  # Too generic
def do_stuff():     # Meaningless
def x():            # Single letter
```

### 2. Function Size & Complexity

**Good - Small, Focused Functions:**
```python
# ✅ EXAMPLE: encryption_service.py (13 lines)
def encrypt(self, plaintext: str) -> str:
    """Encrypt plaintext string."""
    try:
        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return base64.b64encode(encrypted_bytes).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise RuntimeError("Failed to encrypt data") from e

# ✅ EXAMPLE: document_processor.py (4 lines)
def generate_key() -> str:
    """Generate new Fernet encryption key."""
    key = Fernet.generate_key()
    return key.decode()
```

**Watch - Complex Functions:**
```python
# ⚠️ TOO COMPLEX - Multiple responsibilities
def final_report_generation(state):
    # Extract config (5 lines)
    # Validate notes (10 lines)
    # Select LLM with fallback (20 lines)
    # Build prompt (15 lines)
    # Invoke LLM (10 lines)
    # Post-process (10 lines)
    # Total: 70+ lines, 6 responsibilities
```

**Standards:**
- Target: Functions < 30 lines
- Critical threshold: 50 lines
- If > 50 lines, must have clear sections and could likely be split
- Single purpose per function

### 3. Single Responsibility Principle

**Excellent - Service Delegation:**
```python
# ✅ EXAMPLE: google_drive_client.py
class GoogleDriveClient:
    """Orchestrator that delegates to specialized services"""

    def __init__(self):
        self.authenticator = GoogleAuthenticator()      # Auth only
        self.metadata_parser = GoogleMetadataParser()   # Parsing only
        self.document_processor = DocumentProcessor()   # Processing only
```

**Excellent - Base Class Lifecycle:**
```python
# ✅ EXAMPLE: base_job.py
class BaseJob:
    """Manages job lifecycle only"""

    def execute(self):
        """Orchestrates: validate → execute → log"""

    def validate_params(self):
        """Parameter validation only"""

    def _execute_job(self):
        """Subclass-specific logic (abstract)"""
```

**Anti-Pattern - Too Many Responsibilities:**
```python
# ❌ ServiceContainer doing too much
class ServiceContainer:
    # 1. Service registration
    # 2. Service creation
    # 3. Caching
    # 4. Thread-safe initialization
    # 5. Lifecycle management
    # 6. Async task tracking

    # Could be split into:
    # - ServiceRegistry (registration)
    # - ServiceLifecycleManager (creation, caching, lifecycle)
```

### 4. Type Hints

**Excellent - 100% Type Coverage:**
```python
# ✅ EXAMPLE: encryption_service.py
def __init__(self, encryption_key: str | None = None):
    """Constructor with optional parameter"""

def encrypt(self, plaintext: str) -> str:
    """Method with return type"""

async def retrieve_context(
    self,
    query: str,
    conversation_history: list[dict] | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Async method with complex types"""
```

**Good - Pydantic Models:**
```python
# ✅ EXAMPLE: settings.py (Pydantic)
class SlackSettings(BaseModel):
    bot_token: str
    app_token: str
    signing_secret: str | None = None
```

**Anti-Pattern - Missing Types:**
```python
# ❌ BAD
def __init__(self, settings, llm_service=None):
    # Missing type hints for parameters

# ❌ BAD
self.api_service = None  # Should be: GoogleDriveAPI | None
```

**Standards:**
- 100% type hints for public methods
- Use union types for optionals: `str | None`
- Type complex structures: `list[dict[str, Any]]`
- Pydantic for configuration classes

### 5. Docstrings

**Excellent - Comprehensive Docstrings:**
```python
# ✅ EXAMPLE: container.py
class ServiceContainer:
    """
    Centralized service registry with dependency injection.

    Features:
    - Singleton pattern for services
    - Lazy initialization
    - Automatic dependency resolution
    - Graceful resource cleanup
    - Thread-safe service creation
    """

def register_factory(self, service_type: type[T], factory: Callable[[], T]):
    """
    Register a factory function for service creation.

    Args:
        service_type: The service type/interface to register
        factory: Async callable that creates the service instance

    Example:
        container.register_factory(
            LLMService,
            lambda: LLMService(settings, rag_service)
        )

    Raises:
        ValueError: If service_type already registered
    """
```

**Good - Args/Returns Format:**
```python
# ✅ EXAMPLE: encryption_service.py
def decrypt(self, ciphertext: str) -> str:
    """
    Decrypt ciphertext string.

    Args:
        ciphertext: Base64-encoded encrypted string

    Returns:
        Decrypted plaintext string

    Raises:
        RuntimeError: If decryption fails
    """
```

**Anti-Pattern - Missing/Weak Docstrings:**
```python
# ❌ TOO BRIEF
class ApiResponse:
    """Generic API response wrapper."""
    # Missing: What fields? What's the structure?

# ❌ MISSING
def extract_text(self, content: bytes, mime_type: str):
    # No docstring at all
```

**Standards:**
- All public classes/functions must have docstrings
- Format: Summary → Args → Returns → Raises → Example (if complex)
- Private methods (_method) can have brief docstrings or none if obvious

### 6. Error Handling

**Excellent - Specific Exceptions with Context:**
```python
# ✅ EXAMPLE: encryption_service.py
try:
    decrypted_bytes = self.cipher.decrypt(ciphertext.encode())
    return decrypted_bytes.decode()
except InvalidToken as e:
    logger.error("Decryption failed - invalid key or corrupted data")
    raise RuntimeError("Failed to decrypt data - invalid encryption key") from e
except Exception as e:
    logger.error(f"Decryption failed: {e}")
    raise RuntimeError("Failed to decrypt data") from e
```

**Best Practices:**
1. Catch specific exceptions first
2. Log with context before re-raising
3. Use `from e` to preserve stack trace
4. Provide user-friendly error messages
5. Include relevant details in logs

**Excellent - Structured Error Returns:**
```python
# ✅ EXAMPLE: base_job.py
except Exception as e:
    execution_time = (datetime.utcnow() - start_time).total_seconds()
    error_type = type(e).__name__
    stack_trace = traceback.format_exc()
    safe_params = sanitize_dict(self.params)  # Security: sanitize

    logger.error(f"Job failed: {self.JOB_NAME} ...")

    return {
        "status": "error",
        "error": str(e),
        "error_type": error_type,
        "execution_time": execution_time,
        "error_context": {...}
    }
```

**Anti-Pattern - Too Broad:**
```python
# ❌ BAD - Broad exception without logging
try:
    result = some_operation()
except Exception as e:  # Too broad
    return []  # Silent failure, no logging
```

**Guard Clauses:**
```python
# ✅ GOOD - Early return pattern
if not self.api_service:
    raise RuntimeError("Not authenticated. Call authenticate() first.")

if not vector_service:
    logger.info("No vector service available")
    return []
```

### 7. Constants & Magic Numbers

**Good - Clear Units:**
```python
# ✅ GOOD
maxBytes=50 * 1024 * 1024  # 50MB - multiplication shows units
backupCount=5

# ✅ BETTER - Named constant
MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
file_handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=MAX_LOG_SIZE_BYTES
)
```

**Good - Configuration Over Hardcoding:**
```python
# ✅ EXCELLENT - settings.py (Pydantic)
class Settings(BaseModel):
    max_chunks: int = Field(default=5)
    similarity_threshold: float = Field(default=0.7)
    timeout_seconds: int = Field(default=30)
```

**Anti-Pattern - Mutable Defaults:**
```python
# ❌ CRITICAL BUG - Mutable default
class BaseJob:
    REQUIRED_PARAMS: list = []  # Shared across instances!
    OPTIONAL_PARAMS: list = []  # Will accumulate modifications

# ✅ CORRECT
class BaseJob:
    REQUIRED_PARAMS: list[str] = []  # Still risky

# ✅ BETTER - Use None and initialize in __init__
class BaseJob:
    def __init__(self):
        self.required_params = []
        self.optional_params = []
```

### 8. Simple Workflows

**Good - Clear Dispatcher Pattern:**
```python
# ✅ EXAMPLE: document_processor.py
def extract_text(self, content: bytes, mime_type: str) -> str | None:
    """Simple dispatch based on MIME type"""
    if mime_type == "application/pdf":
        return self._extract_pdf_text(content)
    elif mime_type == "application/vnd...docx":
        return self._extract_docx_text(content)
    elif mime_type == "application/vnd...xlsx":
        return self._extract_xlsx_text(content)
    else:
        logger.warning(f"Unsupported MIME type: {mime_type}")
        return None
```

**Anti-Pattern - Complex Nested Logic:**
```python
# ❌ COMPLEX - Multi-level async with state tracking
async with self._lock:
    if service_type in self._services:
        return self._services[service_type]

    if service_type in self._initializing:
        await self._initializing[service_type]
        return self._services[service_type]

    task = asyncio.create_task(...)
    self._initializing[service_type] = task
    # ... more complexity
```

**Anti-Pattern - Implicit Fallback:**
```python
# ❌ UNCLEAR - Dynamic imports with implicit fallback
llm = None
if settings.gemini.enabled and settings.gemini.api_key:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(...)
    except ImportError:
        # Falls back to OpenAI (not obvious from code)
```

### 9. Dependency Injection

**Excellent - Constructor Injection:**
```python
# ✅ EXAMPLE: rag_service.py
def __init__(self, settings: Settings):
    """All dependencies passed in or created from settings"""
    self.settings = settings
    self.vector_store = create_vector_store(settings.vector)
    self.embedding_provider = create_embedding_provider(settings)
    self.llm_provider = create_llm_provider(settings.llm)
```

**Good - Context Managers:**
```python
# ✅ EXAMPLE: models/base.py
@contextmanager
def get_db_session():
    """Context manager for automatic cleanup"""
    if _SessionLocal is None:
        init_db(get_settings().task_database_url)

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

### 10. Logging

**Excellent - Structured Logging:**
```python
# ✅ EXAMPLE: logging.py
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "exception": self.formatException(record.exc_info) if record.exc_info else None
        })
```

**Good - Contextual Logging:**
```python
# ✅ EXAMPLE: base_job.py
logger.info(
    f"Starting job: {self.JOB_NAME} (ID: {self.job_id})"
)
# ... later ...
logger.info(
    f"Job completed: {self.JOB_NAME} "
    f"(ID: {self.job_id}, Duration: {execution_time:.2f}s)"
)
```

---

### 11. Performance Patterns (NEW)

**Critical - N+1 Query Problem:**
```python
# ❌ CRITICAL - N+1 query (fetches user for each post)
def get_user_posts(user_id: int) -> list[dict]:
    posts = Post.query.filter_by(user_id=user_id).all()
    for post in posts:
        post.author = User.query.get(post.author_id)  # N queries!
    return posts

# ✅ GOOD - Eager loading (1 query with join)
def get_user_posts(user_id: int) -> list[dict]:
    posts = Post.query.filter_by(user_id=user_id).options(
        joinedload(Post.author)  # Load author in same query
    ).all()
    return posts

# ✅ BETTER - Explicit join for complex queries
def get_user_posts(user_id: int) -> list[dict]:
    posts = session.query(Post).join(User).filter(
        Post.user_id == user_id
    ).all()
    return posts
```

**Critical - Inefficient Algorithms:**
```python
# ❌ CRITICAL - O(n²) list concatenation
def process_items(items: list[str]) -> list[str]:
    result = []
    for item in items:
        result = result + [item]  # Creates new list each time!
    return result

# ✅ GOOD - O(n) append
def process_items(items: list[str]) -> list[str]:
    result = []
    for item in items:
        result.append(item)  # In-place modification
    return result

# ✅ BETTER - List comprehension (fastest)
def process_items(items: list[str]) -> list[str]:
    return [process(item) for item in items]

# ❌ CRITICAL - Repeated expensive operations
def find_users(user_ids: list[int]) -> list[User]:
    users = []
    for user_id in user_ids:
        user = User.query.get(user_id)  # N queries!
        users.append(user)
    return users

# ✅ GOOD - Single query with IN clause
def find_users(user_ids: list[int]) -> list[User]:
    return User.query.filter(User.id.in_(user_ids)).all()
```

**High - Inefficient String Operations:**
```python
# ❌ HIGH - String concatenation in loop
def build_report(items: list[str]) -> str:
    report = ""
    for item in items:
        report += f"- {item}\n"  # Creates new string each iteration
    return report

# ✅ GOOD - Join (O(n) instead of O(n²))
def build_report(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)

# ✅ GOOD - StringIO for large outputs
from io import StringIO

def build_large_report(items: list[str]) -> str:
    buffer = StringIO()
    for item in items:
        buffer.write(f"- {item}\n")
    return buffer.getvalue()
```

**Medium - Missing Database Indexes:**
```python
# ❌ MEDIUM - Full table scan on frequently queried column
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255))  # No index, but frequently queried!

# Query is slow:
user = User.query.filter_by(email=email).first()  # Table scan!

# ✅ GOOD - Add index on frequently queried columns
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), index=True)  # Index for fast lookups

# ✅ BETTER - Unique index if appropriate
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True)
```

**Detection Patterns:**
```python
# CRITICAL severity
- ORM queries inside loops (User.query.get in for loop)
- result = result + [item] pattern (list concatenation in loop)
- Nested loops with O(n²) or worse complexity

# HIGH severity
- String concatenation in loops (str += str)
- Multiple separate queries that could be joined
- Missing .options(joinedload()) on relationships

# MEDIUM severity
- No index on frequently filtered columns
- Inefficient sorting (manual sort vs database ORDER BY)
- Loading entire table when only subset needed (.all() without filter)

# Detection Commands:
grep -r "\.query\.get\|\.query\.filter" --include="*.py" -A5 -B5 | grep "for "
grep -r "result.*=.*result.*+" --include="*.py"
grep -r "Column(" --include="*.py" | grep -v "index=True"
```

---

### 12. Concurrency Safety (NEW)

**Critical - Race Conditions:**
```python
# ❌ CRITICAL - Race condition (shared state without lock)
class Counter:
    def __init__(self):
        self.count = 0

    async def increment(self):
        # Multiple coroutines can read same value
        self.count += 1  # Not atomic!

# ✅ GOOD - asyncio.Lock for shared state
class Counter:
    def __init__(self):
        self.count = 0
        self._lock = asyncio.Lock()

    async def increment(self):
        async with self._lock:
            self.count += 1  # Protected by lock

# ✅ BETTER - Thread-safe primitives
from threading import Lock

class Counter:
    def __init__(self):
        self.count = 0
        self._lock = Lock()

    def increment(self):
        with self._lock:
            self.count += 1
```

**Critical - Async/Await Misuse:**
```python
# ❌ CRITICAL - Blocking call in async function
async def process_data():
    data = requests.get("https://api.example.com/data")  # Blocks event loop!
    return data.json()

# ✅ GOOD - Use async HTTP client
import httpx

async def process_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# ❌ CRITICAL - Missing await
async def save_user(user):
    update_database(user)  # Should be: await update_database(user)
    # Continues without waiting for database write!

# ✅ GOOD - Always await async calls
async def save_user(user):
    await update_database(user)  # Wait for completion
```

**High - Deadlock Risk:**
```python
# ❌ HIGH - Potential deadlock (inconsistent lock ordering)
class BankAccount:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.balance = 0

async def transfer(from_account, to_account, amount):
    async with from_account._lock:  # Lock A
        async with to_account._lock:  # Lock B
            from_account.balance -= amount
            to_account.balance += amount

# If two transfers happen simultaneously in opposite directions:
# Transfer 1: A → B (locks A, then tries B)
# Transfer 2: B → A (locks B, then tries A)
# Deadlock!

# ✅ GOOD - Consistent lock ordering
async def transfer(from_account, to_account, amount):
    # Always lock in same order (by ID)
    accounts = sorted([from_account, to_account], key=lambda a: a.id)
    async with accounts[0]._lock:
        async with accounts[1]._lock:
            from_account.balance -= amount
            to_account.balance += amount
```

**Medium - Event Loop Blocking:**
```python
# ❌ MEDIUM - CPU-intensive work in async function
async def process_large_file():
    with open("large.csv") as f:
        data = f.read()  # Blocks!
        # CPU-intensive parsing
        for line in data.split('\n'):
            process_line(line)  # Blocks event loop!

# ✅ GOOD - Use run_in_executor for blocking I/O
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def process_large_file():
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        data = await loop.run_in_executor(executor, read_file, "large.csv")
        # Or use ProcessPoolExecutor for CPU-intensive work
        result = await loop.run_in_executor(executor, process_data, data)
    return result

# ✅ BETTER - Use aiofiles for async file I/O
import aiofiles

async def process_large_file():
    async with aiofiles.open("large.csv", mode='r') as f:
        data = await f.read()
    # Process in chunks to avoid blocking
    return process_data(data)
```

**Detection Patterns:**
```python
# CRITICAL severity
- Shared mutable state (class attributes, instance vars) modified in async methods without locks
- Blocking calls in async functions (requests.get, time.sleep, open() without executor)
- Missing await on async function calls

# HIGH severity
- Multiple locks acquired in inconsistent order
- No timeout on lock acquisition (can hang forever)
- Using threading.Lock in asyncio code (use asyncio.Lock)

# MEDIUM severity
- CPU-intensive work in async functions without run_in_executor
- Synchronous file I/O in async functions
- Large in-memory operations blocking event loop

# Detection Commands:
grep -r "async def" --include="*.py" -A10 | grep "requests\.\|time\.sleep\|open("
grep -r "self\.[a-z_]*\s*=" --include="*.py" | grep "async def" -B5
grep -r "async def.*:$" --include="*.py" -A10 | grep -v "await "
```

---

### 13. Resource Management (NEW)

**Critical - Memory Leaks:**
```python
# ❌ CRITICAL - Unbounded cache (memory leak)
class CacheService:
    def __init__(self):
        self.cache = {}  # Grows forever!

    def set(self, key, value):
        self.cache[key] = value  # Never evicts old entries

# ✅ GOOD - Size-limited cache with LRU eviction
from functools import lru_cache
from cachetools import LRUCache

class CacheService:
    def __init__(self, max_size=1000):
        self.cache = LRUCache(maxsize=max_size)  # Evicts LRU when full

    def set(self, key, value):
        self.cache[key] = value

# ✅ BETTER - TTL + size limits
from cachetools import TTLCache

class CacheService:
    def __init__(self):
        self.cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hour TTL
```

**Critical - Unclosed Resources:**
```python
# ❌ CRITICAL - File never closed (resource leak)
def read_config():
    f = open("config.json")
    data = json.load(f)
    return data  # File handle leaks if exception occurs

# ✅ GOOD - Context manager ensures cleanup
def read_config():
    with open("config.json") as f:
        data = json.load(f)
    return data

# ❌ CRITICAL - Database connection not closed
def get_users():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()  # Connection leaks!

# ✅ GOOD - Use context manager
def get_users():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            return cursor.fetchall()

# ✅ BETTER - Use connection pool
from sqlalchemy import create_engine

engine = create_engine(DATABASE_URL, pool_size=10)

def get_users():
    with engine.connect() as conn:
        result = conn.execute("SELECT * FROM users")
        return result.fetchall()
```

**High - Circular References:**
```python
# ❌ HIGH - Circular reference (prevents garbage collection)
class Node:
    def __init__(self, value):
        self.value = value
        self.parent = None
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        child.parent = self  # Circular reference!

# Memory isn't freed even when tree is no longer referenced

# ✅ GOOD - Use weakref to break cycle
import weakref

class Node:
    def __init__(self, value):
        self.value = value
        self.parent = None  # Will be weak reference
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        child.parent = weakref.ref(self)  # Weak reference

    def get_parent(self):
        return self.parent() if self.parent else None
```

**Medium - Large Object Retention:**
```python
# ❌ MEDIUM - Retaining large objects unnecessarily
class DataProcessor:
    def __init__(self):
        self.raw_data = None  # Retained after processing!

    def process_file(self, filename):
        with open(filename) as f:
            self.raw_data = f.read()  # 100MB file

        result = self._process(self.raw_data)
        return result  # raw_data still in memory!

# ✅ GOOD - Release large objects when done
class DataProcessor:
    def process_file(self, filename):
        with open(filename) as f:
            raw_data = f.read()

        result = self._process(raw_data)
        del raw_data  # Explicit cleanup
        return result

# ✅ BETTER - Process in chunks
class DataProcessor:
    def process_file(self, filename):
        result = []
        with open(filename) as f:
            for chunk in iter(lambda: f.read(1024 * 1024), ''):  # 1MB chunks
                result.append(self._process_chunk(chunk))
        return result
```

**Medium - Resource Pool Exhaustion:**
```python
# ❌ MEDIUM - Connection pool exhaustion
from sqlalchemy import create_engine

# Default pool_size=5, max_overflow=10
engine = create_engine(DATABASE_URL)

def get_all_users():
    connections = []
    for i in range(20):  # Opens 20 connections!
        conn = engine.connect()
        connections.append(conn)
    # Pool exhausted, other requests block

# ✅ GOOD - Proper connection management
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=3600
)

def get_all_users():
    with engine.connect() as conn:  # Returns to pool when done
        return conn.execute("SELECT * FROM users").fetchall()
```

**Detection Patterns:**
```python
# CRITICAL severity
- open() without context manager or .close()
- Database connections without context manager
- Unbounded dict/list used as cache (no size limit)
- HTTP clients created but never closed

# HIGH severity
- Circular references without weakref
- Large objects stored as instance attributes
- Missing __del__ or cleanup methods for resources

# MEDIUM severity
- Connection pool exhaustion (many connections opened)
- Files read entirely into memory (no streaming)
- Response objects not closed after use

# Detection Commands:
grep -r "open(" --include="*.py" | grep -v "with "
grep -r "\.connect(" --include="*.py" | grep -v "with "
grep -r "self\.[a-z_]*\s*=\s*{}" --include="*.py"
grep -r "self\.[a-z_]*\s*=\s*\[\]" --include="*.py" | grep -v "__init__"
```

---

### 14. Code Duplication (NEW)

**High - Repeated Logic:**
```python
# ❌ HIGH - Same validation logic repeated
def create_user(email: str, name: str) -> User:
    if not email or '@' not in email:
        raise ValueError("Invalid email")
    if not name or len(name) < 2:
        raise ValueError("Invalid name")
    return User(email=email, name=name)

def update_user(user_id: int, email: str, name: str) -> User:
    if not email or '@' not in email:  # Duplicated!
        raise ValueError("Invalid email")
    if not name or len(name) < 2:  # Duplicated!
        raise ValueError("Invalid name")
    user = User.query.get(user_id)
    user.email = email
    user.name = name
    return user

# ✅ GOOD - Extract validation
def validate_email(email: str) -> None:
    if not email or '@' not in email:
        raise ValueError("Invalid email")

def validate_name(name: str) -> None:
    if not name or len(name) < 2:
        raise ValueError("Invalid name")

def create_user(email: str, name: str) -> User:
    validate_email(email)
    validate_name(name)
    return User(email=email, name=name)

def update_user(user_id: int, email: str, name: str) -> User:
    validate_email(email)
    validate_name(name)
    user = User.query.get(user_id)
    user.email = email
    user.name = name
    return user

# ✅ BETTER - Use Pydantic for validation
from pydantic import BaseModel, EmailStr, constr

class UserInput(BaseModel):
    email: EmailStr  # Built-in email validation
    name: constr(min_length=2)  # Name validation

def create_user(data: UserInput) -> User:
    return User(email=data.email, name=data.name)
```

**High - Similar Functions:**
```python
# ❌ HIGH - Nearly identical functions (copy-paste)
def get_user_by_id(user_id: int) -> User | None:
    user = User.query.filter_by(id=user_id).first()
    if not user:
        logger.warning(f"User not found: {user_id}")
        return None
    return user

def get_post_by_id(post_id: int) -> Post | None:
    post = Post.query.filter_by(id=post_id).first()
    if not post:
        logger.warning(f"Post not found: {post_id}")
        return None
    return post

def get_comment_by_id(comment_id: int) -> Comment | None:
    comment = Comment.query.filter_by(id=comment_id).first()
    if not comment:
        logger.warning(f"Comment not found: {comment_id}")
        return None
    return comment

# ✅ GOOD - Generic function with type parameter
from typing import TypeVar, Type

T = TypeVar('T')

def get_by_id(model: Type[T], id: int) -> T | None:
    instance = model.query.filter_by(id=id).first()
    if not instance:
        logger.warning(f"{model.__name__} not found: {id}")
        return None
    return instance

# Usage:
user = get_by_id(User, user_id)
post = get_by_id(Post, post_id)
comment = get_by_id(Comment, comment_id)
```

**Medium - Repeated Patterns:**
```python
# ❌ MEDIUM - Same error handling repeated
def process_user_data(user_id: int):
    try:
        user = get_user(user_id)
        result = process(user)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error processing user: {e}")
        return {"status": "error", "message": str(e)}

def process_post_data(post_id: int):
    try:
        post = get_post(post_id)
        result = process(post)
        return {"status": "success", "data": result}
    except Exception as e:  # Same pattern!
        logger.error(f"Error processing post: {e}")
        return {"status": "error", "message": str(e)}

# ✅ GOOD - Decorator for error handling
from functools import wraps

def handle_errors(entity_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return {"status": "success", "data": result}
            except Exception as e:
                logger.error(f"Error processing {entity_name}: {e}")
                return {"status": "error", "message": str(e)}
        return wrapper
    return decorator

@handle_errors("user")
def process_user_data(user_id: int):
    user = get_user(user_id)
    return process(user)

@handle_errors("post")
def process_post_data(post_id: int):
    post = get_post(post_id)
    return process(post)
```

**Detection Patterns:**
```python
# HIGH severity
- Functions with >70% similar code (structural similarity)
- Validation logic repeated across multiple functions
- Same try/except pattern in multiple functions

# MEDIUM severity
- Similar function names with incremental numbers (func1, func2, func3)
- Repeated conditional patterns
- Copy-paste errors (wrong variable names in duplicated code)

# LOW severity
- Similar but intentionally different logic
- Domain-specific duplicates (different business rules)

# Detection Commands:
# Use tools like pylint with duplicate-code checker
pylint --disable=all --enable=duplicate-code **/*.py

# Or simjava/simian for similarity detection
# Or manual inspection of similar-looking functions
```

## Anti-Patterns to Detect

### 1. Mutable Default Arguments
```python
# ❌ CRITICAL
class BaseJob:
    REQUIRED_PARAMS: list = []  # Shared mutable default

# Detection: Look for class attributes with mutable defaults (list, dict, set)
# Severity: Critical
```

### 2. Missing Type Hints
```python
# ❌ Warning for public methods without types
def process(data):
    return data

# Detection: Check all public methods for parameter and return types
# Severity: Warning
```

### 3. Functions > 50 Lines
```python
# ⚠️ Complexity warning
def large_function():
    # ... 80 lines of code

# Detection: Count lines in function body (excluding docstring/comments)
# Severity: Warning if > 50, Critical if > 100
```

### 4. Missing Docstrings
```python
# ❌ Public class/function without docstring
class ImportantService:
    pass

def public_api():
    pass

# Detection: Check all public classes and methods
# Severity: Warning
```

### 5. Broad Exception Handling
```python
# ❌ Too generic without logging
try:
    result = operation()
except Exception:  # Too broad
    return None  # Silent failure

# Detection: except Exception without logger.error
# Severity: Warning
```

### 6. Deep Nesting
```python
# ❌ Nesting > 4 levels
if condition1:
    if condition2:
        if condition3:
            if condition4:
                if condition5:  # Too deep!

# Detection: Count indentation levels
# Severity: Warning if > 3, Critical if > 5
```

### 7. Magic Numbers
```python
# ❌ Unexplained constants
timeout = 30  # What's 30? seconds? minutes?
max_size = 5242880  # Unclear

# ✅ Better
TIMEOUT_SECONDS = 30
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

# Detection: Look for numeric literals not in arithmetic
# Severity: Suggestion
```

## Audit Workflow

### Phase 1: Discovery
1. Find all production Python files:
   - `**/*.py` (exclude tests/ directories)
   - Focus on services, models, APIs, utilities
   - Skip test files, migrations, generated code

2. Categorize files:
   - Services (services/*.py)
   - Models (models/*.py)
   - API endpoints (api/*.py)
   - Jobs (jobs/*.py)
   - Utilities (utils/*.py, config/*.py)

### Phase 2: Analysis
For each file:
1. **Naming** - Check classes, functions, variables
2. **Type Hints** - Coverage percentage
3. **Docstrings** - Presence and quality
4. **Function Size** - Lines per function
5. **Complexity** - Nesting depth, branches
6. **Error Handling** - Try/except patterns
7. **SRP** - Lines of responsibility per class/function
8. **Constants** - Magic numbers, mutable defaults
9. **DI** - Constructor injection patterns
10. **Logging** - Usage and context

### Phase 3: Report Generation
```markdown
# Code Audit Report

## Summary
- Total files analyzed: 250
- Total classes: 450
- Total functions: 1,200
- Overall score: 85/100

## Violations by Severity

### Critical (Fix Immediately)
1. module.py:line - Mutable default argument (PARAM: list = [])
2. service.py:line - Function too large (>100 lines)

### Warning (Fix Soon)
1. module.py:line - Missing type hints
2. model.py:line - Missing docstring
3. service.py:line - Broad exception handling without logging

### Suggestion (Consider)
1. module.py:line - Magic number (use named constant)
2. service.py:line - Function could be split (30-50 lines)

## Priority Mapping for Action Planning

**IMPORTANT: Warnings are P1 priority issues and must be treated with the same urgency as Critical violations.**

### P1 - High Priority (Fix ASAP)
- **Critical violations** - Correctness issues, bugs, security risks
- **Warning violations** - Quality issues that impact maintainability, readability, and team velocity
- **Impact:** Blocks code quality goals, slows development, creates technical debt
- **Timeline:** Address immediately in current sprint/iteration

**Examples:**
- Missing type hints (hinders IDE support, static analysis)
- Missing docstrings (blocks team understanding)
- Functions > 50 lines (violates SRP, hard to test)
- Broad exception handling (masks bugs, silent failures)
- Deep nesting > 3 levels (cognitive complexity)

### P2 - Medium Priority (Fix When Convenient)
- **Suggestion violations** - Nice-to-haves, polish items
- **Impact:** Minor quality improvements, consistency
- **Timeline:** Address in next sprint or refactoring cycle

**Examples:**
- Magic numbers (could use constants)
- Functions 30-50 lines (could be split but not urgent)

### P3 - Low Priority (Optional)
- **Polish items** - Style preferences, minor optimizations
- **Impact:** Minimal
- **Timeline:** Address during major refactoring or if time permits

## Quality Metrics

| Metric | Score | Target |
|--------|-------|--------|
| Type Hint Coverage | 92% | 95% |
| Docstring Coverage | 87% | 90% |
| Avg Function Size | 22 lines | < 30 |
| Max Nesting Depth | 4 levels | < 4 |
| Magic Numbers | 12 | 0 |

## Best Practice Examples

[Link to excellent examples in codebase for learning]

## Detailed Findings

[File-by-file breakdown]
```

### Phase 4: Recommendations
For each violation:
1. **Show the problem** with code excerpt
2. **Explain the risk** (bugs, maintainability, testing)
3. **Provide the fix** with code example
4. **Reference standard** from this document

## Agent Execution Commands

### Full Audit
```
Run comprehensive code audit across all services.
Analyze: naming, types, docstrings, complexity, error handling, SRP, best practices.
Generate detailed report with severity levels and metrics.
```

### Quick Audit (Specific Service)
```
Audit [service_name] production code only.
Focus on critical violations.
```

### Specific Checks
```
Check type hint coverage across all services
Scan for mutable default arguments (critical bug risk)
Find functions > 50 lines
Identify missing docstrings on public APIs
```

## Success Criteria

After running the agent and applying recommendations:
- ✅ 95%+ type hint coverage
- ✅ 90%+ docstring coverage
- ✅ No critical violations
- ✅ < 5% warning violations
- ✅ All functions < 50 lines
- ✅ No mutable defaults
- ✅ No silent exception swallowing

## Integration with Development

### When to Run
- Before pull requests
- After major feature additions
- Weekly as part of quality checks
- Before releases

### Continuous Improvement
- Track metric trends
- Celebrate improvements
- Share best examples
- Update standards based on evolution

---

## Implementation Notes

**Tools Needed:**
- AST parsing for code structure
- Complexity analysis (cyclomatic complexity)
- Type hint checker integration
- Pattern matching for anti-patterns

**Exemplar Files** (Find and learn from these):
- Config/settings modules - Type hints & validation
- Service modules with good error handling - Error handling & docstrings
- Well-structured API clients - SRP & delegation
- Logging utilities - Structured logging
- Dependency injection containers - DI patterns

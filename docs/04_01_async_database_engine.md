# 04_01 — Async Database Engine

**Parent:** 04 Async FastAPI + WebSocket
**Must complete before:** 04_02 (endpoint migration depends on async sessions)

---

## Objective

Add an async SQLAlchemy engine alongside the existing sync engine. The API
layer uses the async engine for non-blocking request handling. Agents, CLI,
and scheduler keep the sync engine unchanged.

---

## Current State (`src/prism/db.py`)

```python
_engine: Engine | None = None

def get_engine(url: str | None = None) -> Engine:
    # synchronous create_engine with check_same_thread=False
    # WAL mode + foreign keys via PRAGMA

def init_db(url: str | None = None) -> Engine:
    # create_all or skip if Alembic-managed

def get_session(engine: Engine | None = None) -> Session:
    return Session(engine or get_engine())
```

All callers — routes, agents, CLI — use the same sync engine.

---

## Design: Dual Engine Architecture

```
┌──────────────────────────────────────────────────┐
│                 src/prism/db.py                    │
│                                                    │
│  Sync Engine (existing)        Async Engine (new)  │
│  ─────────────────────        ──────────────────── │
│  get_engine() → Engine        get_async_engine()   │
│  get_session() → Session        → AsyncEngine      │
│                                get_async_session()  │
│  Used by:                       → AsyncSession     │
│  - APScheduler agents                              │
│  - CLI commands               Used by:             │
│  - Alembic migrations         - FastAPI endpoints  │
│  - init_db()                                       │
└──────────────────────────────────────────────────┘
```

**Why dual engines:**
- Agents run in APScheduler threads — they need synchronous DB access
- FastAPI runs in an asyncio event loop — async DB avoids blocking
- Mixing sync calls inside `async def` handlers blocks the event loop
- SQLite WAL mode supports concurrent readers from both engines

---

## Implementation

### Changes to `src/prism/db.py`

```python
import logging
from contextlib import asynccontextmanager

from sqlalchemy import Engine, event, inspect
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Session, SQLModel, create_engine

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_async_engine: AsyncEngine | None = None


# ── SQLite Pragmas ──────────────────────────────────────────────────

def _apply_sqlite_pragmas(engine: Engine) -> None:
    """Set WAL mode and foreign keys for sync engine."""
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _apply_async_sqlite_pragmas(async_engine: AsyncEngine) -> None:
    """Set WAL mode and foreign keys for async engine."""
    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ── Sync Engine (agents, CLI, scheduler) ────────────────────────────

def get_engine(url: str | None = None) -> Engine:
    """Get or create the synchronous SQLAlchemy engine."""
    global _engine
    if _engine is None or url is not None:
        if url is None:
            from prism.config import settings
            url = settings.database_url
        _engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        _apply_sqlite_pragmas(_engine)
    return _engine


def get_session(engine: Engine | None = None) -> Session:
    """Create a synchronous session (for agents and CLI)."""
    return Session(engine or get_engine())


# ── Async Engine (FastAPI endpoints) ────────────────────────────────

def _to_async_url(url: str) -> str:
    """Convert sync SQLite URL to async aiosqlite URL.

    'sqlite:///data/newsgen.db' → 'sqlite+aiosqlite:///data/newsgen.db'
    """
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def get_async_engine(url: str | None = None) -> AsyncEngine:
    """Get or create the async SQLAlchemy engine."""
    global _async_engine
    if _async_engine is None or url is not None:
        if url is None:
            from prism.config import settings
            url = settings.database_url
        async_url = _to_async_url(url)
        _async_engine = create_async_engine(
            async_url,
            echo=False,
        )
        _apply_async_sqlite_pragmas(_async_engine)
    return _async_engine


@asynccontextmanager
async def get_async_session():
    """Yield an async session for FastAPI dependency injection.

    Usage in routes:
        async def handler(session: AsyncSession = Depends(get_async_session)):
            result = await session.exec(select(Source))
    """
    engine = get_async_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            await session.close()


# ── Init (unchanged — uses sync engine) ─────────────────────────────

def _is_alembic_managed(engine: Engine) -> bool:
    insp = inspect(engine)
    return "alembic_version" in insp.get_table_names()


def init_db(url: str | None = None) -> Engine:
    """Create all tables (sync). Returns the sync engine."""
    import prism.models  # noqa: F401
    engine = get_engine(url)
    if _is_alembic_managed(engine):
        logger.info("Database is managed by Alembic — skipping create_all")
    else:
        SQLModel.metadata.create_all(engine)
    return engine


# ── Cleanup ─────────────────────────────────────────────────────────

async def close_async_engine() -> None:
    """Dispose the async engine. Call on application shutdown."""
    global _async_engine
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        logger.info("Async engine disposed")
```

---

## URL Conversion

SQLite sync and async drivers use different URL schemes:

| Engine | URL scheme | Driver |
|--------|-----------|--------|
| Sync | `sqlite:///data/newsgen.db` | built-in `sqlite3` |
| Async | `sqlite+aiosqlite:///data/newsgen.db` | `aiosqlite` |

The `_to_async_url()` helper converts automatically. Both point to the
same physical database file. SQLite WAL mode allows concurrent access.

**Non-SQLite databases:** if `DATABASE_URL` is Postgres
(`postgresql://...`), the conversion would use `asyncpg`. This is out
of scope for now — document for future reference.

---

## FastAPI Dependency

Replace the existing `_get_session` in `routes.py`:

```python
# Before (sync)
def _get_session():
    from prism.db import get_engine
    with Session(get_engine()) as session:
        yield session

# After (async)
async def _get_async_session():
    from prism.db import get_async_session
    async with get_async_session() as session:
        yield session
```

The sync `_get_session` is NOT removed — it's still used by the webhook
endpoint (02_03) which calls Stripe SDK synchronously. Keep both available.

---

## AsyncSession Usage Patterns

### Read (select)

```python
# Sync
stories = session.exec(select(StoryCluster)).all()

# Async
result = await session.exec(select(StoryCluster))
stories = result.all()
```

**Important:** `await session.exec()` returns a `Result` object, not the
rows directly. Call `.all()`, `.first()`, or `.one()` on the result.

### Read (get by ID)

```python
# Sync
user = session.get(User, user_id)

# Async
user = await session.get(User, user_id)
```

### Write

```python
# Sync
session.add(engagement)
session.commit()
session.refresh(engagement)

# Async
session.add(engagement)
await session.commit()
await session.refresh(engagement)
```

### Relationships (lazy loading)

SQLAlchemy async sessions cannot lazy-load relationships. Use explicit
queries instead:

```python
# Sync (lazy load works)
cluster = session.get(StoryCluster, story_id)
articles = cluster.articles  # lazy-loaded

# Async (explicit query required)
cluster = await session.get(StoryCluster, story_id)
result = await session.exec(
    select(Article).where(Article.cluster_id == story_id)
)
articles = result.all()
```

This is already the pattern used in `routes.py` (see `get_story` at line
441-449) — no change needed for existing relationship queries.

---

## `expire_on_commit=False`

Set on the async session to prevent expired-attribute access after commit:

```python
AsyncSession(engine, expire_on_commit=False)
```

Without this, accessing `briefing.id` after `await session.commit()` would
raise a `MissingGreenlet` error because SQLAlchemy tries to lazy-refresh
the expired attribute in a sync context.

---

## App Lifecycle Hooks

Register engine cleanup in `src/prism/api/app.py`:

```python
from contextlib import asynccontextmanager
from prism.db import close_async_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_async_engine()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Prism API",
        lifespan=lifespan,
        # ...
    )
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Async engine creates with aiosqlite URL | Verify `sqlite+aiosqlite:///` in engine URL |
| 2 | Async session reads from the same DB file | Write with sync, read with async, verify data |
| 3 | WAL mode enabled on async engine | `PRAGMA journal_mode` returns `wal` via async |
| 4 | Foreign keys enforced on async engine | Insert invalid FK via async, verify error |
| 5 | Sync engine still works for agents | Run `discovery_cycle()`, verify articles stored |
| 6 | Sync engine still works for CLI | Run `prism story ls`, verify output |
| 7 | `get_async_session` yields and cleans up | Use in test, verify session closed after block |
| 8 | `close_async_engine` disposes cleanly | Call on shutdown, verify no open connections |
| 9 | `_to_async_url` converts SQLite URLs correctly | Unit test with various URL formats |
| 10 | Concurrent async reads don't block | `asyncio.gather` 10 selects, verify all return |
| 11 | Concurrent async + sync access works | Async read while sync writes, verify no lock error |

---

## Testing Strategy

### Unit Tests

```python
def test_to_async_url_sqlite():
    assert _to_async_url("sqlite:///data/db.sqlite") == "sqlite+aiosqlite:///data/db.sqlite"

def test_to_async_url_memory():
    assert _to_async_url("sqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"

def test_to_async_url_non_sqlite():
    """Non-SQLite URLs pass through unchanged."""
    assert _to_async_url("postgresql://host/db") == "postgresql://host/db"

@pytest.mark.asyncio
async def test_async_session_reads(async_engine, populated_db):
    """Async session can read rows written by sync engine."""
    async with get_async_session() as session:
        result = await session.exec(select(Source))
        sources = result.all()
        assert len(sources) > 0

@pytest.mark.asyncio
async def test_async_session_writes(async_engine):
    """Async session can write and read back."""
    async with get_async_session() as session:
        source = Source(name="Test", url="https://test.com")
        session.add(source)
        await session.commit()
        await session.refresh(source)
        assert source.id is not None

@pytest.mark.asyncio
async def test_concurrent_async_reads(async_engine, populated_db):
    """10 concurrent reads complete without errors."""
    async def read_sources():
        async with get_async_session() as session:
            result = await session.exec(select(Source))
            return result.all()

    results = await asyncio.gather(*[read_sources() for _ in range(10)])
    assert all(len(r) > 0 for r in results)
```

### Regression

All existing sync tests pass unchanged — sync engine and `get_session()`
are untouched.

---

## Dependencies (New)

```toml
aiosqlite = ">=0.20"
```

Add to `pyproject.toml` under `[project.dependencies]`.

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/db.py` | Add async engine, session, URL converter, cleanup |
| `src/prism/api/app.py` | Add lifespan handler for async engine disposal |
| `pyproject.toml` | Add aiosqlite dependency |
| `tests/test_db_async.py` | New test file |

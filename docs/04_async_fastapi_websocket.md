# 04 — Async FastAPI + WebSocket Support

**Priority:** 4 (Scale)
**Depends on:** None (backend-only refactor)
**Unlocks:** Real-time dashboard updates, better concurrency, horizontal scaling path

---

## Objective

Migrate FastAPI from synchronous to asynchronous handlers and add WebSocket
endpoints for live updates. This removes the sync bottleneck identified in
`docs/architecture_proposal__5_6_2026.md` and enables real-time push to the
frontend.

---

## Current State

- All FastAPI endpoints use `def` (synchronous)
- Database access via synchronous `Session` from SQLModel
- APScheduler runs all agent cycles synchronously in-process
- No WebSocket support — frontend must poll for updates

---

## Implementation Tasks

### 1. Async Database Engine

Replace synchronous SQLAlchemy engine with async variant.

**Changes to `src/prism/db.py`:**

```python
# Current
from sqlmodel import create_engine, Session

# Target
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel
```

- Swap `sqlite:///` with `sqlite+aiosqlite:///` in connection string
- Replace `Session` context manager with `AsyncSession`
- All DB operations use `await session.exec(...)` instead of `session.exec(...)`
- Keep synchronous engine available for APScheduler agent cycles
  (agents run in background threads, not in async event loop)

**New dependency:** `aiosqlite`

### 2. Async Endpoint Migration

Convert all 23 API endpoints from `def` to `async def`.

**Pattern:**

```python
# Before
@router.get("/stories")
def list_stories(session: Session = Depends(get_session)):
    stories = session.exec(select(StoryCluster)).all()
    return stories

# After
@router.get("/stories")
async def list_stories(session: AsyncSession = Depends(get_async_session)):
    result = await session.exec(select(StoryCluster))
    stories = result.all()
    return stories
```

**Migration order (by risk):**

1. Read-only endpoints first: `/health`, `/sources`, `/stories`, `/config`, `/metrics`
2. Authenticated reads: `/users/{id}`, `/briefings`, `/keywords`
3. Write endpoints: `POST /users`, `POST /engagements`, `POST /keywords`
4. Complex endpoints: `POST /briefings` (triggers W_AI), `/checkout`, `/webhooks`

### 3. Async Rate Limiter

Current rate limiter uses synchronous dict access. Migration:

- Replace with `asyncio.Lock` for counter updates
- Or use `aiolimiter` library for token-bucket rate limiting
- Maintain same limits: 60 rpm (public), 120 rpm (authenticated)

### 4. WebSocket Endpoints

**WS /ws/briefings/{user_id}**

- Auth: API key sent as query param or first message
- Pushes new briefing notification when W_AI completes a cycle
- Payload: `{type: "briefing", briefing_id, story_count, created_at}`
- Frontend replaces polling with persistent connection

**WS /ws/perception**

- Auth: API key as query param
- Pushes perception snapshot updates after R_AI scan cycle
- Payload: `{type: "perception", keyword_id, keyword, perception, momentum, computed_at}`
- Frontend perception dashboard updates in real-time

**WS /ws/stories**

- No auth required (public data)
- Pushes new analyzed stories as A_AI completes analysis
- Payload: `{type: "story", cluster_id, headline, resonance_score, categories}`
- Frontend dashboard shows live story feed

**Connection management:**

```python
# src/prism/api/websocket.py
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}  # channel → connections

    async def connect(self, channel: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(channel, []).append(ws)

    async def broadcast(self, channel: str, data: dict):
        for ws in self.active.get(channel, []):
            try:
                await ws.send_json(data)
            except WebSocketDisconnect:
                self.active[channel].remove(ws)
```

### 5. Agent-to-WebSocket Bridge

Agent cycles run synchronously in APScheduler threads. To push updates to
WebSocket clients:

- After each agent cycle completes, publish event to an `asyncio.Queue`
- Background async task reads from queue and broadcasts via ConnectionManager
- Thread-safe bridge: use `loop.call_soon_threadsafe()` from agent thread

```
APScheduler thread          asyncio event loop
      |                            |
      |-- queue.put(event) ------->|
      |                            |-- ConnectionManager.broadcast()
      |                            |        |
      |                            |        v
      |                            |   WebSocket clients
```

### 6. Graceful Shutdown

- On SIGTERM: stop accepting new WebSocket connections
- Close existing WebSocket connections with 1001 (Going Away) code
- Wait for in-flight async requests to complete (uvicorn graceful shutdown)
- APScheduler shutdown remains unchanged

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/db.py` | Add async engine factory + `get_async_session` dependency |
| `src/prism/api/routes.py` | Convert all handlers to `async def`, use `AsyncSession` |
| `src/prism/api/rate_limit.py` | Async-compatible rate limiter |
| `src/prism/api/websocket.py` | New file: ConnectionManager + WS endpoints |
| `src/prism/api/app.py` | Register WS routes, startup/shutdown hooks for manager |
| `src/prism/main.py` | Add queue bridge between APScheduler and async loop |
| `src/prism/config.py` | Add `WEBSOCKET_HEARTBEAT_SEC` (default 30) |
| `pyproject.toml` | Add `aiosqlite` dependency |

---

## Backward Compatibility

- All REST endpoints keep identical request/response schemas
- Agents continue to use synchronous DB sessions (no async migration needed)
- CLI commands unaffected (they use synchronous engine directly)
- Existing tests continue to work with `httpx.AsyncClient` (TestClient adapter)

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | All REST endpoints return identical responses after migration | Run full API test suite, zero regressions |
| 2 | Async endpoints handle concurrent requests without blocking | Load test: 50 concurrent requests, verify <500ms p95 |
| 3 | WebSocket connection establishes and receives heartbeat | Connect with `websocat`, verify ping every 30s |
| 4 | Briefing WebSocket pushes notification after W_AI cycle | Trigger briefing, verify WS client receives event |
| 5 | Perception WebSocket pushes after R_AI scan | Trigger perception scan, verify WS client receives event |
| 6 | Story WebSocket pushes after A_AI analysis | Trigger analysis, verify WS client receives event |
| 7 | WebSocket auth rejects invalid API keys | Connect with bad key, verify connection closed with 4003 |
| 8 | Rate limiter works correctly under async | Fire 70 requests in 1s (public), verify 429 after 60 |
| 9 | Graceful shutdown closes WebSocket connections cleanly | Send SIGTERM, verify clients receive 1001 close code |
| 10 | Agent cycles still work (sync APScheduler) | Run `prism cycle discover`, verify articles stored |
| 11 | Database WAL mode still functions with async engine | Run concurrent reads + writes, verify no lock errors |

---

## Testing Strategy

- **Migrate existing tests** to use `httpx.AsyncClient` with `ASGITransport`
- **WebSocket tests:** use `httpx_ws` or `starlette.testclient.TestClient`
- **Concurrency tests:** async load tests with `asyncio.gather` for parallel requests
- **Regression:** full test suite must pass with zero modifications to assertions

---

## Performance Targets

| Metric | Current (sync) | Target (async) |
|--------|----------------|----------------|
| Concurrent requests | ~10 (thread pool) | ~100+ (event loop) |
| p95 latency (GET /stories) | ~200ms | <100ms |
| WebSocket push latency | N/A (polling) | <500ms from event |
| Memory per connection | N/A | <50KB per WebSocket |

---

## Dependencies (New)

```
aiosqlite>=0.20     — async SQLite driver
```

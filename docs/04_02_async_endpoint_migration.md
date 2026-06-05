# 04_02 — Async Endpoint Migration

**Parent:** 04 Async FastAPI + WebSocket
**Depends on:** 04_01 (async database engine + session dependency)

---

## Objective

Convert all 23 FastAPI endpoint handlers from synchronous `def` to
asynchronous `async def` using the new async database session. Every
endpoint must return identical request/response schemas — this is a
transparent internal refactor.

---

## Migration Pattern

Every endpoint follows the same conversion:

```python
# BEFORE
@router.get("/endpoint")
def handler(session: Session = Depends(_get_session)):
    rows = session.exec(select(Model)).all()
    return [SchemaOut.model_validate(r) for r in rows]

# AFTER
@router.get("/endpoint")
async def handler(session: AsyncSession = Depends(_get_async_session)):
    result = await session.exec(select(Model))
    rows = result.all()
    return [SchemaOut.model_validate(r) for r in rows]
```

**Three changes per endpoint:**
1. `def` → `async def`
2. `Session` → `AsyncSession` (from `_get_async_session`)
3. `session.exec(...)` → `result = await session.exec(...)` then `result.all()`
4. `session.get(Model, id)` → `await session.get(Model, id)`
5. `session.commit()` → `await session.commit()`
6. `session.refresh(obj)` → `await session.refresh(obj)`

---

## Migration Order (by risk)

### Phase 1 — Read-only public endpoints (lowest risk)

| Endpoint | Handler | Async changes |
|----------|---------|---------------|
| `GET /health` | `health()` | `async def` only — no DB call |
| `GET /health/live` | `health_live()` | `async def` only — no DB call |
| `GET /health/ready` | `health_ready()` | `await session.exec(select(Source).limit(1))` |
| `GET /metrics` | `metrics()` | `async def` only — reads in-memory metrics |
| `GET /config` | `config()` | `async def` only — reads settings |
| `GET /sources` | `list_sources()` | `await session.exec(stmt)` |
| `GET /stories` | `list_stories()` | `await session.exec(stmt)` |
| `GET /stories/{id}` | `get_story()` | `await session.get()` + 2× `await session.exec()` |
| `GET /stories/{id}/resonance` | `get_story_resonance()` | `await session.get()` + `await session.exec()` |
| `GET /keywords` | `list_keywords()` | `await session.exec(stmt)` |
| `GET /keywords/{id}/perception` | `get_keyword_perception()` | `await session.get()` + `await session.exec()` |
| `GET /keywords/{id}/perception/history` | `get_keyword_perception_history()` | `await session.get()` + `await session.exec()` |

**Verification:** run all `test_api_*.py` tests after phase 1.

### Phase 2 — Authenticated read endpoints

| Endpoint | Handler | Notes |
|----------|---------|-------|
| `GET /users/{id}` | `get_user()` | Auth dep also needs async |
| `GET /users/{id}/briefings` | `list_briefings()` | Auth + pagination |
| `GET /users/{id}/briefings/{id}` | `get_briefing()` | Auth + detail |

### Phase 3 — Write endpoints

| Endpoint | Handler | Notes |
|----------|---------|-------|
| `POST /users` | `create_user()` | Calls `register_user()` — see below |
| `PATCH /users/{id}` | `update_user()` | Auth + `await session.commit()` |
| `POST /engagements` | `create_engagement()` | Auth + `await session.commit()` |
| `POST /keywords` | `create_keyword()` | `await session.commit()` |
| `DELETE /keywords/{id}` | `deactivate_keyword()` | `await session.commit()` |

### Phase 4 — Complex endpoints

| Endpoint | Handler | Notes |
|----------|---------|-------|
| `POST /users/{id}/briefings` | `trigger_briefing()` | Calls P_AI + W_AI sync — needs `run_in_executor` |
| `POST /users/{id}/checkout` | `create_checkout()` | Calls Stripe SDK sync — needs `run_in_executor` |
| `POST /users/{id}/portal` | `create_portal_session()` | Calls Stripe SDK sync — needs `run_in_executor` |
| `POST /webhooks/stripe` | `stripe_webhook()` | Already async (reads raw body) |

---

## Auth Dependency Migration

The `require_api_key` dependency does a DB lookup — it must also become async.

```python
# BEFORE
def require_api_key(
    api_key: str | None = Security(_api_key_header),
    session: Session = Depends(_get_session),
) -> User:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    key_hash = hash_api_key(api_key)
    user = session.exec(
        select(User).where(User.api_key_hash == key_hash)
    ).first()
    ...

# AFTER
async def require_api_key(
    api_key: str | None = Security(_api_key_header),
    session: AsyncSession = Depends(_get_async_session),
) -> User:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    key_hash = hash_api_key(api_key)
    result = await session.exec(
        select(User).where(User.api_key_hash == key_hash)
    )
    user = result.first()
    ...
```

---

## Handling Sync Library Calls in Async Endpoints

Three endpoints call synchronous libraries that cannot be awaited:

### `POST /users/{id}/briefings` — calls P_AI + W_AI

P_AI and W_AI use sync DB sessions and sync Claude/Resend API calls.
Wrap in `run_in_executor` to avoid blocking the event loop:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="prism-sync")

@router.post("/users/{user_id}/briefings", response_model=BriefingDetailOut, status_code=201)
async def trigger_briefing(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    session: AsyncSession = Depends(_get_async_session),
) -> BriefingDetailOut:
    if auth_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Run sync agent code in thread pool
    loop = asyncio.get_running_loop()
    briefing = await loop.run_in_executor(
        _executor,
        _sync_generate_briefing,
        user,
    )

    if briefing is None:
        raise HTTPException(status_code=422, detail="No stories available")

    return BriefingDetailOut.model_validate(briefing)


def _sync_generate_briefing(user: User) -> Briefing | None:
    """Run P_AI + W_AI synchronously in a thread."""
    from prism.agents.p_ai import PersonalizationAgent
    from prism.agents.w_ai import WriterAgent
    from prism.db import get_engine

    engine = get_engine()
    p_ai = PersonalizationAgent()
    w_ai = WriterAgent()
    stories = p_ai.select_stories(user, engine=engine)
    return w_ai.create_and_send(user, stories, engine=engine)
```

### `POST /users/{id}/checkout` and `/portal` — calls Stripe SDK

Same pattern: wrap `stripe.checkout.Session.create()` and
`stripe.billing_portal.Session.create()` in `run_in_executor`.

```python
checkout_session = await loop.run_in_executor(
    _executor,
    lambda: stripe.checkout.Session.create(...)
)
```

---

## `POST /users` — `register_user()` Adapter

`register_user()` in `onboarding.py` uses a sync engine internally. Two options:

**Option A (recommended):** keep it sync, wrap in `run_in_executor`:
```python
@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate) -> UserOut:
    loop = asyncio.get_running_loop()
    try:
        user = await loop.run_in_executor(
            _executor,
            lambda: register_user(
                email=body.email,
                interests=body.interests,
                briefing_depth=body.briefing_depth,
            ),
        )
    except RegistrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return UserOut.model_validate(user)
```

**Option B:** rewrite `register_user()` to accept async session. Deferred —
higher risk, no user-facing benefit.

---

## Test Migration

### Test Client Changes

FastAPI TestClient with `httpx` supports both sync and async apps:

```python
# BEFORE
from fastapi.testclient import TestClient
client = TestClient(app)
res = client.get("/stories")

# AFTER (no change needed for basic tests)
from fastapi.testclient import TestClient
client = TestClient(app)  # TestClient wraps async app transparently
res = client.get("/stories")
```

`TestClient` from Starlette handles async apps by running an internal
event loop. **Existing tests work without changes** as long as the
dependency override provides the right session type.

### Dependency Override for Tests

```python
# BEFORE
def override_get_session():
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[_get_session] = override_get_session

# AFTER — override the async dependency
async def override_get_async_session():
    async with AsyncSession(test_async_engine, expire_on_commit=False) as session:
        yield session

app.dependency_overrides[_get_async_session] = override_get_async_session
```

If some tests still use the sync override (for webhook tests), keep both.

---

## Verification Strategy

For each migration phase:

1. Convert endpoints
2. Run the corresponding `test_api_*.py` file
3. Verify all assertions pass with zero changes
4. Run full suite (`pytest tests/`) to check for regressions

**Zero assertion changes** is the success criterion. If any test needs
modified assertions, the migration introduced a behavioral change — fix it.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | All 23 endpoints return identical JSON after migration | Diff API responses before/after for all endpoints |
| 2 | All existing API tests pass without assertion changes | `pytest tests/test_api_*.py` exits 0 |
| 3 | Auth dependency works with async session | Authenticated endpoint returns 200 with valid key |
| 4 | Auth rejects invalid key (async path) | Verify 401 response |
| 5 | `POST /users` creates user via run_in_executor | Create user, verify row in DB |
| 6 | `POST /briefings` generates briefing via run_in_executor | Trigger briefing, verify response |
| 7 | Thread pool is bounded (max 4 workers) | Verify `_executor._max_workers == 4` |
| 8 | Sync agents still work after migration | Run `prism cycle discover`, verify success |
| 9 | CLI still works after migration | Run `prism story ls`, verify output |
| 10 | OpenAPI docs still generate correctly | Visit `/docs`, verify all endpoints listed |

---

## Testing Strategy

- **Regression:** run full `pytest` suite — zero failures is the only pass criterion
- **Concurrency:** `asyncio.gather` 20 parallel `GET /stories`, verify all 200
- **Thread safety:** trigger 3 concurrent `POST /briefings`, verify no DB corruption
- **Manual:** `curl` every endpoint, diff JSON with pre-migration responses

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/routes.py` | Convert all 23 handlers + `require_api_key` to async |
| `tests/conftest.py` | Add async session dependency override |
| `tests/test_api_*.py` | Update dependency override references (if needed) |

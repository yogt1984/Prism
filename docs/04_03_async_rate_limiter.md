# 04_03 — Async Rate Limiter

**Parent:** 04 Async FastAPI + WebSocket
**Depends on:** 04_02 (endpoints are async, middleware must match)

---

## Objective

Replace the synchronous sliding-window rate limiter with an async-safe
implementation. The current `RateLimitMiddleware` uses a plain `dict` and
`deque` without locking — safe in sync single-threaded mode but racy under
async concurrent requests.

---

## Current State (`src/prism/api/rate_limit.py`)

```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    # Per-IP sliding window
    # _hits: dict[str, deque[float]]  — no lock protection
    # public_rpm=60, authenticated_rpm=120, window=60s
    async def dispatch(self, request, call_next):
        # reads/writes _hits without lock
```

**Problem:** under async, multiple concurrent requests from the same IP
can read `_hits` simultaneously, leading to race conditions where the
count is underreported and the limit is not enforced.

---

## Solution: `asyncio.Lock` per IP

Replace the bare dict access with a lock. Using one global lock would
serialize all rate-limit checks (defeating the async benefit). Instead,
use a per-IP lock stored alongside the deque.

---

## Implementation

```python
"""Async-safe sliding-window in-memory rate limiter middleware."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Paths exempt from rate limiting (e.g., Stripe webhooks)
_EXEMPT_PATHS: set[str] = {"/webhooks/stripe"}


@dataclass
class _ClientBucket:
    """Per-client rate limit state."""
    timestamps: deque[float] = field(default_factory=deque)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP async-safe sliding-window rate limiter.

    Args:
        app: The ASGI application.
        public_rpm: Requests per minute for unauthenticated requests.
        authenticated_rpm: Requests per minute for authenticated requests.
        window_seconds: Sliding window size in seconds.
    """

    def __init__(
        self,
        app,
        public_rpm: int = 60,
        authenticated_rpm: int = 120,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.public_rpm = public_rpm
        self.authenticated_rpm = authenticated_rpm
        self.window_seconds = window_seconds
        self._buckets: dict[str, _ClientBucket] = {}
        self._cleanup_counter = 0
        self._cleanup_interval = 100  # run cleanup every N requests

    def _get_client_ip(self, request: Request) -> str:
        if request.client:
            return request.client.host
        return "unknown"

    def _clean_window(self, timestamps: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Skip WebSocket connections (they have their own auth)
        if request.url.path.startswith("/ws/"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        # Get or create bucket for this client
        if client_ip not in self._buckets:
            self._buckets[client_ip] = _ClientBucket()
        bucket = self._buckets[client_ip]

        # Acquire per-client lock for thread-safe counter update
        async with bucket.lock:
            self._clean_window(bucket.timestamps, now)

            has_api_key = bool(request.headers.get("X-API-Key"))
            limit = self.authenticated_rpm if has_api_key else self.public_rpm

            if len(bucket.timestamps) >= limit:
                retry_after = int(
                    self.window_seconds - (now - bucket.timestamps[0])
                ) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": str(retry_after)},
                )

            bucket.timestamps.append(now)

        # Periodic cleanup of stale client entries
        self._cleanup_counter += 1
        if self._cleanup_counter >= self._cleanup_interval:
            self._cleanup_counter = 0
            self._cleanup_stale_buckets(now)

        return await call_next(request)

    def _cleanup_stale_buckets(self, now: float) -> None:
        """Remove buckets for clients with no recent activity."""
        cutoff = now - self.window_seconds * 2
        stale = [
            ip for ip, bucket in self._buckets.items()
            if not bucket.timestamps or bucket.timestamps[-1] < cutoff
        ]
        for ip in stale:
            del self._buckets[ip]
```

---

## Key Design Decisions

### Per-IP Lock (not global)

A single global lock would serialize all rate-limit checks:

```
Request A (IP 1) acquires lock → check → release
Request B (IP 2) waits for lock → check → release   ← unnecessary wait
```

Per-IP locks allow concurrent rate limiting for different clients:

```
Request A (IP 1) acquires lock_1 → check → release
Request B (IP 2) acquires lock_2 → check → release   ← parallel
```

Lock contention only occurs for concurrent requests from the **same IP**,
which is exactly when rate limiting matters.

### Memory Cleanup

Without cleanup, `_buckets` grows unboundedly as new IPs arrive. The
periodic cleanup (every 100 requests) removes entries with no activity
in the last 2 windows (120 seconds). This keeps memory bounded.

**Estimated memory:** each bucket is ~200 bytes (deque + lock). At 10,000
unique IPs, that's ~2MB — negligible.

### Exempt Paths

Stripe webhooks (`/webhooks/stripe`) are exempt because Stripe sends
legitimate bursts of events. WebSocket paths (`/ws/*`) are exempt because
they're long-lived connections, not request/response.

---

## Backward Compatibility

| Aspect | Before | After |
|--------|--------|-------|
| Public limit | 60 rpm | 60 rpm (unchanged) |
| Authenticated limit | 120 rpm | 120 rpm (unchanged) |
| Window | 60s sliding | 60s sliding (unchanged) |
| 429 response body | `{"detail": "Too many requests"}` | Identical |
| Retry-After header | Present | Present (unchanged) |
| Webhook exemption | Not implemented | Added |
| WebSocket exemption | N/A | Added |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Public rate limit enforced at 60 rpm | Send 61 requests in 1s, verify 61st returns 429 |
| 2 | Authenticated rate limit enforced at 120 rpm | Send 121 with API key, verify 121st returns 429 |
| 3 | Retry-After header present on 429 | Inspect response headers |
| 4 | Different IPs rate-limited independently | Send 60 from IP A and 60 from IP B, verify all 200 |
| 5 | Concurrent requests from same IP are counted correctly | `asyncio.gather` 70 requests, verify exactly 60 succeed |
| 6 | Stale buckets cleaned up | Send 1 request, wait 2 windows, verify bucket removed |
| 7 | Webhook path exempt from rate limiting | Send 200 requests to `/webhooks/stripe`, verify no 429 |
| 8 | WebSocket path exempt from rate limiting | Verify `/ws/stories` not rate-limited |
| 9 | Window slides correctly | Send 60 at T=0, wait 61s, send 1 at T=61, verify 200 |

---

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_rate_limit_enforced(client):
    """61st request within window returns 429."""
    for i in range(60):
        res = client.get("/health")
        assert res.status_code == 200
    res = client.get("/health")
    assert res.status_code == 429
    assert "Retry-After" in res.headers

@pytest.mark.asyncio
async def test_rate_limit_authenticated_higher(client, api_key):
    """Authenticated clients get 120 rpm."""
    for i in range(120):
        res = client.get("/health", headers={"X-API-Key": api_key})
        assert res.status_code == 200
    res = client.get("/health", headers={"X-API-Key": api_key})
    assert res.status_code == 429

@pytest.mark.asyncio
async def test_webhook_exempt(client):
    """Webhook path is not rate-limited."""
    for i in range(200):
        res = client.post("/webhooks/stripe", content=b"{}")
        # May return 400 (bad signature) but not 429
        assert res.status_code != 429

@pytest.mark.asyncio
async def test_concurrent_same_ip_counted(client):
    """Concurrent requests from same IP all counted."""
    import asyncio
    responses = await asyncio.gather(*[
        asyncio.to_thread(client.get, "/health")
        for _ in range(70)
    ])
    ok_count = sum(1 for r in responses if r.status_code == 200)
    assert ok_count == 60  # exactly 60 pass

def test_stale_bucket_cleanup():
    """Stale buckets are removed after 2 windows."""
    middleware = RateLimitMiddleware(app=None)
    bucket = _ClientBucket()
    bucket.timestamps.append(0.0)  # very old
    middleware._buckets["1.2.3.4"] = bucket
    middleware._cleanup_stale_buckets(now=300.0)
    assert "1.2.3.4" not in middleware._buckets
```

### Regression

All existing rate limit tests pass with identical assertions.

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/rate_limit.py` | Replace implementation with async-safe version |
| `tests/test_rate_limit.py` | Update for async + add concurrency tests |

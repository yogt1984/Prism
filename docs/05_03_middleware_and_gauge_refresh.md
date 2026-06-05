# 05_03 — Metrics Middleware & Gauge Refresh Job

**Parent:** 05 Prometheus Metrics Export
**Depends on:** 05_02 (metrics defined with labels)

---

## Objective

Implement two data flows into the Prometheus metrics:

1. **HTTP middleware** — auto-instruments every request with duration
   histogram and request counter (replaces manual `api_requests_total.inc()`).
2. **Gauge refresh job** — APScheduler job that updates point-in-time
   gauges (active sources, users, clusters, circuit breaker state) from
   the database every 5 minutes.

---

## Part 1: Metrics Middleware

### File: `src/prism/api/middleware.py` (new)

```python
"""FastAPI middleware for automatic request metrics."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from prism.metrics import api_requests_total, prism_api_request_duration_seconds


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count and duration for every HTTP request."""

    async def dispatch(self, request: Request, call_next):
        # Skip metrics for /metrics itself to avoid recursion noise
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Normalize path: collapse /stories/123 → /stories/{id}
        endpoint = self._normalize_path(request.url.path)

        prism_api_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        api_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=str(response.status_code),
        ).inc()

        return response

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Collapse numeric path segments to {id} to prevent label explosion.

        /stories/42 → /stories/{id}
        /users/5/briefings/12 → /users/{id}/briefings/{id}
        /keywords/3/perception/history → /keywords/{id}/perception/history
        """
        parts = path.strip("/").split("/")
        normalized = []
        for part in parts:
            if part.isdigit():
                normalized.append("{id}")
            else:
                normalized.append(part)
        return "/" + "/".join(normalized) if normalized else "/"
```

### Register in `src/prism/api/app.py`

```python
from prism.api.middleware import MetricsMiddleware

def create_app() -> FastAPI:
    app = FastAPI(...)
    app.add_middleware(MetricsMiddleware)   # before rate limiter
    app.add_middleware(RateLimitMiddleware)
    app.include_router(router)
    return app
```

**Middleware order matters:** `MetricsMiddleware` wraps the full request
including rate-limited 429s, so it captures all responses.

### Remove Manual Counter

Remove the manual `api_requests_total.inc()` from `routes.py` if it
exists in any endpoint — the middleware now handles it globally.

---

## Part 2: Gauge Refresh Job

### File: `src/prism/metrics_refresh.py` (new)

```python
"""Periodic gauge refresh — updates point-in-time metrics from DB."""

import logging

from sqlalchemy import Engine, func
from sqlmodel import Session, select

from prism.circuit_breaker import brave_breaker, claude_breaker
from prism.metrics import (
    prism_sources_active,
    prism_clusters_total,
    prism_users_total,
    prism_keywords_active,
    prism_circuit_breaker_state,
)
from prism.models import KeywordTrack, Source, StoryCluster, User

logger = logging.getLogger(__name__)


def refresh_gauges(engine: Engine) -> None:
    """Query database and update Prometheus gauges."""
    with Session(engine) as session:
        # Active sources
        active_sources = session.exec(
            select(func.count(Source.id)).where(Source.active == True)
        ).one()
        prism_sources_active.set(active_sources)

        # Clusters by status
        for status in ("raw", "analyzed"):
            count = session.exec(
                select(func.count(StoryCluster.id)).where(
                    StoryCluster.status == status
                )
            ).one()
            prism_clusters_total.labels(status=status).set(count)

        # Users by tier
        free_count = session.exec(
            select(func.count(User.id)).where(User.is_pro == False)
        ).one()
        pro_count = session.exec(
            select(func.count(User.id)).where(User.is_pro == True)
        ).one()
        prism_users_total.labels(tier="free").set(free_count)
        prism_users_total.labels(tier="pro").set(pro_count)

        # Active keywords
        kw_count = session.exec(
            select(func.count(KeywordTrack.id)).where(
                KeywordTrack.is_active == True
            )
        ).one()
        prism_keywords_active.set(kw_count)

    # Circuit breaker state (no DB needed)
    prism_circuit_breaker_state.labels(service="brave_api").set(
        brave_breaker.get_state_value()
    )
    prism_circuit_breaker_state.labels(service="claude_api").set(
        claude_breaker.get_state_value()
    )

    logger.debug("Gauge refresh complete")
```

### Register Job in `src/prism/main.py`

Add to `build_scheduler()` after existing jobs:

```python
from prism.metrics_refresh import refresh_gauges

scheduler.add_job(
    lambda: refresh_gauges(get_engine()),
    "interval",
    minutes=5,
    id="gauge_refresh",
)
```

This runs in APScheduler's thread pool alongside agent cycles.

---

## Path Normalization — Label Explosion Prevention

Without normalization, each unique story ID creates a new label
combination, consuming Prometheus memory unboundedly:

```
prism_api_request_duration_seconds{endpoint="/stories/1"} ...
prism_api_request_duration_seconds{endpoint="/stories/2"} ...
prism_api_request_duration_seconds{endpoint="/stories/3"} ...
```

After normalization:
```
prism_api_request_duration_seconds{endpoint="/stories/{id}"} ...
```

Expected cardinality: ~15 unique endpoint patterns (matching the 23
route definitions collapsed by ID segments).

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Every HTTP request increments `api_requests_total` | Make 5 requests, verify counter=5 |
| 2 | Request duration histogram populated | Make request, verify bucket counts in /metrics |
| 3 | Path normalized: `/stories/42` → `/stories/{id}` | Request `/stories/1`, verify label |
| 4 | `/metrics` endpoint itself excluded from metrics | Verify no `endpoint="/metrics"` label |
| 5 | `prism_sources_active` reflects DB state | Add source, wait for refresh, verify gauge |
| 6 | `prism_users_total{tier="pro"}` correct | Create pro user, verify gauge |
| 7 | `prism_clusters_total{status="raw"}` correct | Store cluster, verify gauge |
| 8 | `prism_circuit_breaker_state` reflects breaker | Trip brave_breaker, verify gauge=1 |
| 9 | Gauge refresh runs every 5 minutes | Check scheduler job list |
| 10 | Rate-limited 429 responses appear in metrics | Exceed limit, verify status_code=429 label |
| 11 | Middleware order: metrics wraps rate limiter | Verify 429 requests counted |

---

## Testing Strategy

### Middleware Tests

```python
def test_metrics_middleware_counts_requests(client):
    """Middleware increments request counter."""
    client.get("/health")
    client.get("/health")
    res = client.get("/metrics")
    body = res.text
    assert 'prism_api_requests_total{' in body
    assert 'endpoint="/health"' in body

def test_path_normalization():
    """Numeric segments collapsed to {id}."""
    from prism.api.middleware import MetricsMiddleware
    assert MetricsMiddleware._normalize_path("/stories/42") == "/stories/{id}"
    assert MetricsMiddleware._normalize_path("/users/5/briefings/12") == "/users/{id}/briefings/{id}"
    assert MetricsMiddleware._normalize_path("/health") == "/health"
    assert MetricsMiddleware._normalize_path("/") == "/"
```

### Gauge Refresh Tests

```python
def test_refresh_gauges_counts_sources(engine, populated_db):
    """Gauge reflects actual source count."""
    refresh_gauges(engine)
    assert prism_sources_active._value.get() > 0

def test_refresh_gauges_circuit_breaker(engine):
    """Circuit breaker gauge reflects state."""
    from prism.circuit_breaker import brave_breaker
    brave_breaker.reset()
    refresh_gauges(engine)
    assert prism_circuit_breaker_state.labels(service="brave_api")._value.get() == 0
    # Trip breaker
    for _ in range(5):
        brave_breaker.record_failure()
    refresh_gauges(engine)
    assert prism_circuit_breaker_state.labels(service="brave_api")._value.get() == 1
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/middleware.py` | New: MetricsMiddleware with path normalization |
| `src/prism/api/app.py` | Register MetricsMiddleware |
| `src/prism/metrics_refresh.py` | New: refresh_gauges function |
| `src/prism/main.py` | Add gauge_refresh job to scheduler |
| `tests/test_middleware.py` | New: middleware + path normalization tests |
| `tests/test_metrics_refresh.py` | New: gauge refresh tests |

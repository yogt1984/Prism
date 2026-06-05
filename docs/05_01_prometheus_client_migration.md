# 05_01 — Prometheus Client Library Migration

**Parent:** 05 Prometheus Metrics Export
**Must complete before:** 05_02 (new metrics depend on prometheus_client types)

---

## Objective

Replace the custom `Counter`, `Gauge`, `Histogram` classes in
`src/prism/metrics.py` with `prometheus_client` equivalents. Every
existing call site (`inc()`, `observe()`, `set()`) must keep working
with zero behavioral change to agents and tests.

---

## Current State (`src/prism/metrics.py`)

Custom dataclass-based metrics with a thread-safe `_registry` dict:

```python
# 11 module-level metric objects:
discovery_articles_total = Counter("discovery_articles_total")
discovery_clusters_stored = Counter("discovery_clusters_stored")
discovery_brave_skip_total = Counter("discovery_brave_skip_total")
analysis_duration_seconds = Histogram("analysis_duration_seconds")
resonance_computed_total = Counter("resonance_computed_total")
perception_computed_total = Counter("perception_computed_total")
briefing_sent_total = Counter("briefing_sent_total")
api_requests_total = Counter("api_requests_total")
cycle_successes_total = Counter("cycle_successes_total")
cycle_failures_total = Counter("cycle_failures_total")
cycle_duration_seconds = Histogram("cycle_duration_seconds")
```

Call sites: `d_ai.py` (line 23), `a_ai.py`, `r_ai.py`, `w_ai.py`,
`routes.py` (line 343–348), `main.py` (via `timed_cycle`).

---

## Implementation

### Step 1: Add Dependency

`pyproject.toml`:
```toml
prometheus_client = ">=0.20"
```

### Step 2: Replace `src/prism/metrics.py`

```python
"""Prometheus-based metrics for the Prism pipeline."""

import functools
import logging
import time
from typing import Any, Callable

from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import CollectorRegistry, REGISTRY

# ── Counters (existing, 1:1 replacement) ─────────────────────────

discovery_articles_total = Counter(
    "prism_discovery_articles_total",
    "Total articles discovered across all cycles",
)
discovery_clusters_stored = Counter(
    "prism_discovery_clusters_stored",
    "Total story clusters stored",
)
discovery_brave_skip_total = Counter(
    "prism_discovery_brave_skip_total",
    "Brave API calls skipped (circuit open)",
)
resonance_computed_total = Counter(
    "prism_resonance_computed_total",
    "Total resonance scores computed",
)
perception_computed_total = Counter(
    "prism_perception_computed_total",
    "Total perception snapshots computed",
)
briefing_sent_total = Counter(
    "prism_briefing_sent_total",
    "Total briefings sent to users",
)
api_requests_total = Counter(
    "prism_api_requests_total",
    "Total API requests received",
)
cycle_successes_total = Counter(
    "prism_cycle_successes_total",
    "Total successful agent cycles",
)
cycle_failures_total = Counter(
    "prism_cycle_failures_total",
    "Total failed agent cycles",
)

# ── Histograms (existing, 1:1 replacement) ───────────────────────

analysis_duration_seconds = Histogram(
    "prism_analysis_duration_seconds",
    "Duration of A_AI analysis cycles",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
)
cycle_duration_seconds = Histogram(
    "prism_cycle_duration_seconds",
    "Duration of agent cycles",
    buckets=(1, 5, 10, 30, 60, 120, 300),
)

# ── timed_cycle decorator (same interface) ───────────────────────

_timed_logger = logging.getLogger("prism.metrics")


def timed_cycle(name: str) -> Callable:
    """Decorator that logs cycle timing/status and updates metrics."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                elapsed = time.monotonic() - start
                cycle_successes_total.inc()
                cycle_duration_seconds.observe(elapsed)
                _timed_logger.info(
                    "Cycle '%s' completed in %.3fs", name, elapsed,
                )
                return result
            except Exception:
                elapsed = time.monotonic() - start
                cycle_failures_total.inc()
                cycle_duration_seconds.observe(elapsed)
                _timed_logger.error(
                    "Cycle '%s' failed after %.3fs", name, elapsed,
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


# ── Snapshot (backward compat for tests) ─────────────────────────

def snapshot() -> dict[str, dict]:
    """JSON snapshot of all prism_ metrics. Used by legacy /metrics."""
    from prometheus_client import REGISTRY
    result = {}
    for metric in REGISTRY.collect():
        if not metric.name.startswith("prism_"):
            continue
        for sample in metric.samples:
            result[sample.name] = {"value": sample.value}
    return result


def reset_all() -> None:
    """Unregister all prism metrics (for testing only)."""
    pass  # prometheus_client handles registry; tests use separate registry
```

### Step 3: Update `/metrics` Endpoint

In `src/prism/api/routes.py`, replace the JSON endpoint (line 343–348):

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

@router.get("/metrics")
async def metrics():
    """Prometheus exposition format metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

Remove `from prism.metrics import snapshot` import from routes.

### Step 4: Naming Convention

All metrics gain a `prism_` prefix to avoid collisions with default
`prometheus_client` process metrics (which expose `process_cpu_seconds`,
`python_gc_objects`, etc. automatically).

| Old name | New name |
|----------|----------|
| `discovery_articles_total` | `prism_discovery_articles_total` |
| `cycle_duration_seconds` | `prism_cycle_duration_seconds` |
| (all others follow same pattern) | |

Call sites import the same Python names (`discovery_articles_total`),
so **zero agent code changes** are needed.

---

## Backward Compatibility

| Aspect | Before | After |
|--------|--------|-------|
| `GET /metrics` | JSON dict | Prometheus text format |
| `discovery_articles_total.inc()` | Custom Counter.inc() | prometheus_client Counter.inc() |
| `cycle_duration_seconds.observe()` | Custom Histogram.observe() | prometheus_client Histogram.observe() |
| `timed_cycle` decorator | Identical interface | Identical interface |
| Default process metrics | Not exposed | Auto-exposed by prometheus_client |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `/metrics` returns valid Prometheus format | `curl /metrics \| promtool check metrics` |
| 2 | All 11 existing metrics appear in output | Grep for `prism_discovery_articles_total` etc. |
| 3 | `timed_cycle` still increments counters | Run discovery, verify counter in output |
| 4 | Agent imports unchanged | `grep "from prism.metrics import" src/` shows same imports |
| 5 | `/metrics` does not require auth | Call without API key, verify 200 |
| 6 | Process metrics auto-exposed | Verify `process_cpu_seconds_total` in output |
| 7 | Existing tests pass after adaptation | `pytest tests/test_metrics.py` exits 0 |

---

## Testing Strategy

```python
def test_metrics_endpoint_prometheus_format(client):
    """Endpoint returns Prometheus exposition format."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    body = res.text
    assert "prism_discovery_articles_total" in body
    assert "prism_cycle_duration_seconds" in body

def test_counter_increments():
    """Counter.inc() works with prometheus_client."""
    from prism.metrics import discovery_articles_total
    before = discovery_articles_total._value.get()
    discovery_articles_total.inc()
    after = discovery_articles_total._value.get()
    assert after == before + 1

def test_histogram_observes():
    """Histogram.observe() works with prometheus_client."""
    from prism.metrics import cycle_duration_seconds
    cycle_duration_seconds.observe(1.5)
    # Verify bucket populated in output
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/metrics.py` | Replace custom classes with prometheus_client |
| `src/prism/api/routes.py` | Update `/metrics` to Prometheus format |
| `pyproject.toml` | Add `prometheus_client>=0.20` |
| `tests/test_metrics.py` | Adapt to prometheus_client API |

# 05_02 — New Metrics, Labels & Agent Instrumentation

**Parent:** 05 Prometheus Metrics Export
**Depends on:** 05_01 (prometheus_client is available)

---

## Objective

Add labeled counters, new gauges, new histograms, and build info.
Update existing counter/histogram calls in agents to include dimension
labels (`agent`, `format`, `method`, `endpoint`, `status_code`).
Update the `timed_cycle` decorator to emit per-agent labels.

---

## New Metrics

### Labeled Counters (replace flat counters)

```python
cycle_successes_total = Counter(
    "prism_cycle_successes_total",
    "Successful agent cycles",
    ["agent"],                          # discovery, analysis, perception, briefing
)
cycle_failures_total = Counter(
    "prism_cycle_failures_total",
    "Failed agent cycles",
    ["agent", "error_type"],
)
briefing_sent_total = Counter(
    "prism_briefing_sent_total",
    "Briefings sent",
    ["format"],                         # email, json_feed, audio_script
)
api_requests_total = Counter(
    "prism_api_requests_total",
    "API requests",
    ["method", "endpoint", "status_code"],
)
discovery_brave_skip_total = Counter(
    "prism_discovery_brave_skip_total",
    "Brave API skips",
    ["reason"],                         # circuit_open, timeout, error
)
```

### New Gauges

```python
prism_sources_active = Gauge(
    "prism_sources_active",
    "Active sources in registry",
)
prism_clusters_total = Gauge(
    "prism_clusters_total",
    "Total story clusters by status",
    ["status"],                         # raw, analyzed
)
prism_users_total = Gauge(
    "prism_users_total",
    "Registered users by tier",
    ["tier"],                           # free, pro
)
prism_keywords_active = Gauge(
    "prism_keywords_active",
    "Active tracked keywords",
)
prism_circuit_breaker_state = Gauge(
    "prism_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"],                        # brave_api, claude_api
)
prism_last_cycle_timestamp = Gauge(
    "prism_last_cycle_timestamp",
    "Unix timestamp of last completed cycle",
    ["agent"],
)
```

### New Histograms

```python
prism_api_request_duration_seconds = Histogram(
    "prism_api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
prism_brave_api_duration_seconds = Histogram(
    "prism_brave_api_duration_seconds",
    "Brave Search API call duration",
    buckets=(0.1, 0.5, 1, 2, 5, 10),
)
prism_claude_api_duration_seconds = Histogram(
    "prism_claude_api_duration_seconds",
    "Claude API call duration",
    ["agent"],                          # analysis, writer, perception
    buckets=(0.5, 1, 2, 5, 10, 30),
)
```

### Build Info

```python
prism_build_info = Info(
    "prism_build_info",
    "Prism build information",
)
# Set once at import time:
import sys
from importlib.metadata import version as pkg_version
try:
    _ver = pkg_version("prism")
except Exception:
    _ver = "0.1.0-dev"
prism_build_info.info({
    "version": _ver,
    "python_version": sys.version.split()[0],
})
```

---

## timed_cycle Update

The decorator must accept the agent name and pass it as a label:

```python
def timed_cycle(name: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                elapsed = time.monotonic() - start
                cycle_successes_total.labels(agent=name).inc()
                cycle_duration_seconds.labels(agent=name).observe(elapsed)
                prism_last_cycle_timestamp.labels(agent=name).set(time.time())
                _timed_logger.info("Cycle '%s' completed in %.3fs", name, elapsed)
                return result
            except Exception as exc:
                elapsed = time.monotonic() - start
                error_type = type(exc).__name__
                cycle_failures_total.labels(agent=name, error_type=error_type).inc()
                cycle_duration_seconds.labels(agent=name).observe(elapsed)
                _timed_logger.error("Cycle '%s' failed after %.3fs", name, elapsed, exc_info=True)
                raise
        return wrapper
    return decorator
```

Adds `agent` label to `cycle_duration_seconds` histogram — requires
updating 05_01's definition to include `["agent"]` labelnames.

---

## Agent Call-Site Updates

### D_AI (`src/prism/agents/d_ai.py`)

```python
# Line 23: import stays the same
from prism.metrics import discovery_brave_skip_total, timed_cycle

# Line 367: add reason label
discovery_brave_skip_total.labels(reason="circuit_open").inc()
```

Add timing around `search_brave`:
```python
from prism.metrics import prism_brave_api_duration_seconds

def search_brave(self, query, count=20):
    start = time.monotonic()
    try:
        # existing code...
        prism_brave_api_duration_seconds.observe(time.monotonic() - start)
        return results
    except Exception:
        prism_brave_api_duration_seconds.observe(time.monotonic() - start)
        raise
```

### A_AI (`src/prism/agents/a_ai.py`)

Add timing around Claude calls:
```python
from prism.metrics import prism_claude_api_duration_seconds

# Around the anthropic.messages.create() call:
start = time.monotonic()
response = self.client.messages.create(...)
prism_claude_api_duration_seconds.labels(agent="analysis").observe(
    time.monotonic() - start
)
```

### W_AI (`src/prism/agents/w_ai.py`)

```python
from prism.metrics import briefing_sent_total, prism_claude_api_duration_seconds

# After sending briefing (existing briefing_sent_total.inc()):
briefing_sent_total.labels(format=user.preferred_format.value).inc()

# Around Claude call:
prism_claude_api_duration_seconds.labels(agent="writer").observe(elapsed)
```

### R_AI (`src/prism/agents/r_ai.py`)

```python
# perception_computed_total.inc() — no label change needed (stays flat)
```

---

## Circuit Breaker Exposure

Add a helper in `src/prism/circuit_breaker.py`:

```python
def get_state_value(self) -> int:
    """Numeric state for Prometheus gauge. 0=closed, 1=open, 2=half_open."""
    state = self.state
    return {"closed": 0, "open": 1, "half_open": 2}[state.value]
```

The gauge refresh job (05_03) reads this value.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `cycle_successes_total` has `agent` label | Run discovery, verify `agent="discovery"` in output |
| 2 | `cycle_failures_total` has `agent` + `error_type` | Force failure, verify labels |
| 3 | `briefing_sent_total` has `format` label | Send email briefing, verify `format="email"` |
| 4 | `api_requests_total` has 3 labels | Make GET /stories, verify method+endpoint+status |
| 5 | `prism_brave_api_duration_seconds` populated | Run discovery, verify histogram buckets |
| 6 | `prism_claude_api_duration_seconds` has agent label | Run analysis, verify `agent="analysis"` |
| 7 | `prism_build_info` shows version | Verify in /metrics output |
| 8 | Gauge definitions present (no values yet) | Verify metric names in output with 0 value |
| 9 | All existing agent tests still pass | `pytest tests/` exits 0 |

---

## Testing Strategy

```python
def test_labeled_cycle_counter():
    """timed_cycle increments with agent label."""
    @timed_cycle("test_agent")
    def dummy():
        pass
    dummy()
    assert cycle_successes_total.labels(agent="test_agent")._value.get() >= 1

def test_labeled_cycle_failure():
    """Failed cycle records error_type label."""
    @timed_cycle("test_agent")
    def failing():
        raise ValueError("boom")
    with pytest.raises(ValueError):
        failing()
    assert cycle_failures_total.labels(
        agent="test_agent", error_type="ValueError"
    )._value.get() >= 1

def test_build_info_present():
    """Build info metric is populated."""
    from prism.metrics import prism_build_info
    # Info metric exists and has version field
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/metrics.py` | Add labeled counters, gauges, histograms, build info |
| `src/prism/agents/d_ai.py` | Add Brave API timing, label skip reason |
| `src/prism/agents/a_ai.py` | Add Claude API timing |
| `src/prism/agents/w_ai.py` | Add format label to briefing counter, Claude timing |
| `src/prism/circuit_breaker.py` | Add `get_state_value()` method |
| `tests/test_metrics.py` | Add label-aware tests |

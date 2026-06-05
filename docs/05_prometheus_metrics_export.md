# 05 — Prometheus Metrics Export

**Priority:** 5 (Scale — Operational Visibility)
**Depends on:** None (standalone)
**Unlocks:** Grafana dashboards, alerting, SLA monitoring

---

## Objective

Expose the existing in-process metrics via a Prometheus-compatible `/metrics`
endpoint and add key observability signals for production monitoring.

---

## Current State

`src/prism/metrics.py` already tracks:

**Counters:**
- `discovery_articles_total`, `discovery_clusters_stored`
- `discovery_brave_skip_total`
- `resonance_computed_total`, `perception_computed_total`
- `briefing_sent_total`
- `api_requests_total`
- `cycle_successes_total`, `cycle_failures_total`

**Histograms:**
- `analysis_duration_seconds`
- `cycle_duration_seconds`

**Decorator:** `@timed_cycle(name)` — wraps agent cycles with timing + status.

**Current exposure:** `GET /metrics` returns JSON snapshot (not Prometheus format).

---

## Implementation Tasks

### 1. Prometheus Client Library

Replace custom metrics implementation with `prometheus_client`:

```python
from prometheus_client import Counter, Histogram, Gauge, Info
```

**Migrate existing metrics:**

| Current Name | Prometheus Type | Labels |
|-------------|-----------------|--------|
| `discovery_articles_total` | Counter | — |
| `discovery_clusters_stored` | Counter | — |
| `discovery_brave_skip_total` | Counter | `reason` (rate_limit, timeout, error) |
| `resonance_computed_total` | Counter | — |
| `perception_computed_total` | Counter | — |
| `briefing_sent_total` | Counter | `format` (email, json_feed, audio_script) |
| `api_requests_total` | Counter | `method`, `endpoint`, `status_code` |
| `cycle_successes_total` | Counter | `agent` (discovery, analysis, perception, briefing) |
| `cycle_failures_total` | Counter | `agent`, `error_type` |
| `analysis_duration_seconds` | Histogram | — |
| `cycle_duration_seconds` | Histogram | `agent` |

### 2. New Metrics

**Gauges (point-in-time values):**

| Metric | Type | Labels | Source |
|--------|------|--------|--------|
| `prism_sources_active` | Gauge | — | Count of `Source.active=True` |
| `prism_clusters_total` | Gauge | `status` (raw, analyzed) | Count by status |
| `prism_users_total` | Gauge | `tier` (free, pro) | Count by tier |
| `prism_keywords_active` | Gauge | — | Count of active KeywordTrack |
| `prism_circuit_breaker_state` | Gauge | `service` (brave, claude, resend) | 0=closed, 1=open |
| `prism_last_cycle_timestamp` | Gauge | `agent` | Unix timestamp of last run |

**Histograms (new):**

| Metric | Type | Labels | Buckets |
|--------|------|--------|---------|
| `prism_api_request_duration_seconds` | Histogram | `method`, `endpoint` | .01, .05, .1, .25, .5, 1, 2.5, 5 |
| `prism_brave_api_duration_seconds` | Histogram | — | .1, .5, 1, 2, 5, 10 |
| `prism_claude_api_duration_seconds` | Histogram | `agent` | .5, 1, 2, 5, 10, 30 |
| `prism_tts_duration_seconds` | Histogram | — | 1, 2, 5, 10, 30, 60 |

**Info:**

| Metric | Fields |
|--------|--------|
| `prism_build_info` | `version`, `python_version`, `prompt_version` |

### 3. Prometheus Endpoint

Replace current JSON `/metrics` with Prometheus exposition format:

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@router.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

Output format (example):

```
# HELP prism_discovery_articles_total Total articles discovered
# TYPE prism_discovery_articles_total counter
prism_discovery_articles_total 1247.0

# HELP prism_cycle_duration_seconds Duration of agent cycles
# TYPE prism_cycle_duration_seconds histogram
prism_cycle_duration_seconds_bucket{agent="discovery",le="1.0"} 0.0
prism_cycle_duration_seconds_bucket{agent="discovery",le="5.0"} 12.0
...
```

### 4. Middleware Instrumentation

Add FastAPI middleware to auto-track request metrics:

```python
@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    prism_api_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)
    api_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
    ).inc()
    return response
```

### 5. Agent Cycle Instrumentation

Update `@timed_cycle` decorator to use `prometheus_client` primitives:

- Increment `cycle_successes_total` / `cycle_failures_total` with `agent` label
- Observe `cycle_duration_seconds` histogram with `agent` label
- Set `prism_last_cycle_timestamp` gauge on completion

### 6. Gauge Refresh Job

Add a lightweight APScheduler job (every 5 minutes) that updates gauges:

```python
def refresh_gauges(session):
    prism_sources_active.set(session.exec(select(func.count(Source.id)).where(Source.active)).one())
    prism_users_total.labels(tier="free").set(...)
    prism_users_total.labels(tier="pro").set(...)
    # ... etc
```

### 7. Docker Compose Updates

Add Prometheus + Grafana services to `docker-compose.prod.yml`:

```yaml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana:latest
  volumes:
    - ./monitoring/dashboards:/var/lib/grafana/dashboards
    - ./monitoring/provisioning:/etc/grafana/provisioning
  ports:
    - "3001:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
```

### 8. Prometheus Scrape Config

`monitoring/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: prism
    scrape_interval: 15s
    static_configs:
      - targets: ["api:8000"]
```

### 9. Grafana Dashboard

Provision a default dashboard (`monitoring/dashboards/prism.json`) with panels:

| Panel | Type | Query |
|-------|------|-------|
| Pipeline Health | Stat | `rate(prism_cycle_successes_total[1h])` |
| Discovery Rate | Graph | `rate(prism_discovery_articles_total[1h])` |
| Analysis Latency | Heatmap | `prism_claude_api_duration_seconds` |
| API Latency p95 | Graph | `histogram_quantile(0.95, prism_api_request_duration_seconds)` |
| Active Users | Stat | `prism_users_total` |
| Circuit Breaker | Status | `prism_circuit_breaker_state` |
| Briefings Sent | Counter | `increase(prism_briefing_sent_total[24h])` |
| Error Rate | Graph | `rate(prism_cycle_failures_total[1h])` |

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/metrics.py` | Replace custom impl with `prometheus_client` |
| `src/prism/api/routes.py` | Update `/metrics` endpoint to Prometheus format |
| `src/prism/api/app.py` | Add metrics middleware |
| `src/prism/main.py` | Add gauge refresh job to scheduler |
| `src/prism/agents/*.py` | Update metric calls to new API |
| `docker-compose.prod.yml` | Add prometheus + grafana services |
| `monitoring/` | New directory: prometheus.yml, dashboards, provisioning |
| `pyproject.toml` | Add `prometheus_client` dependency |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `/metrics` returns valid Prometheus exposition format | `curl /metrics`, parse with `promtool check metrics` |
| 2 | All existing counters appear in output | Compare metric names with current `metrics.py` |
| 3 | API request duration is tracked per endpoint | Make requests, verify histogram buckets populated |
| 4 | Agent cycle metrics include agent label | Run discovery cycle, verify `agent="discovery"` label |
| 5 | Gauges reflect actual database state | Compare `prism_sources_active` with `SELECT COUNT(*)` |
| 6 | Circuit breaker state is exposed | Trip breaker, verify gauge changes to 1 |
| 7 | Prometheus scrapes successfully | Check Prometheus targets page shows "UP" |
| 8 | Grafana dashboard loads with data | Open dashboard, verify all panels render |
| 9 | Existing JSON metrics tests still pass | Run test suite, verify no regressions |
| 10 | Metrics endpoint does not require auth | Call without API key, verify 200 response |

---

## Testing Strategy

- **Unit:** verify metric increments, histogram observations, gauge values
- **Integration:** start server, make requests, scrape `/metrics`, parse output
- **Regression:** existing `test_metrics.py` adapted to new prometheus_client API

---

## Dependencies (New)

```
prometheus_client>=0.20
```

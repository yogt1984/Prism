# 05_04 — Prometheus & Grafana Docker Setup

**Parent:** 05 Prometheus Metrics Export
**Depends on:** 05_03 (metrics endpoint and gauges operational)

---

## Objective

Add Prometheus and Grafana services to the production Docker Compose
stack. Configure Prometheus to scrape the Prism API `/metrics` endpoint.
Provision a default Grafana dashboard with panels for pipeline health,
latency, users, and errors.

---

## Docker Compose Services

### File: `docker-compose.prod.yml` (additions)

```yaml
services:
  # ... existing api service ...

  prometheus:
    image: prom/prometheus:v2.53.0
    restart: unless-stopped
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=30d"
      - "--storage.tsdb.retention.size=5GB"
    depends_on:
      - api

  grafana:
    image: grafana/grafana:11.1.0
    restart: unless-stopped
    volumes:
      - ./monitoring/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/dashboards:/var/lib/grafana/dashboards:ro
      - grafana_data:/var/lib/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

---

## Prometheus Configuration

### File: `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "prism-api"
    metrics_path: /metrics
    static_configs:
      - targets: ["api:8000"]
        labels:
          instance: "prism"
```

**Key decisions:**
- 15s scrape interval: balances resolution vs load (Prism is low-traffic)
- `api:8000`: Docker service name resolves within compose network
- No auth on `/metrics`: endpoint is public (same as `/health`)

---

## Grafana Provisioning

### Datasource: `monitoring/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### Dashboard Provider: `monitoring/provisioning/dashboards/default.yml`

```yaml
apiVersion: 1

providers:
  - name: "Prism"
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

---

## Grafana Dashboard

### File: `monitoring/dashboards/prism.json`

Dashboard with 8 panels in a 2-column grid layout:

| Panel | Type | Row | Query |
|-------|------|-----|-------|
| Pipeline Health | Stat (green/red) | 1 | `sum(rate(prism_cycle_successes_total[1h]))` |
| Cycle Errors (1h) | Stat (red) | 1 | `sum(rate(prism_cycle_failures_total[1h]))` |
| Discovery Rate | Time series | 2 | `rate(prism_discovery_articles_total[1h])` |
| Analysis Latency p95 | Time series | 2 | `histogram_quantile(0.95, rate(prism_cycle_duration_seconds_bucket{agent="analysis"}[5m]))` |
| API Latency p95 | Time series | 3 | `histogram_quantile(0.95, rate(prism_api_request_duration_seconds_bucket[5m]))` |
| API Request Rate | Time series | 3 | `sum(rate(prism_api_requests_total[5m])) by (status_code)` |
| Active Users | Stat | 4 | `prism_users_total` |
| Briefings Sent (24h) | Stat | 4 | `sum(increase(prism_briefing_sent_total[24h]))` |
| Circuit Breaker Status | State timeline | 5 | `prism_circuit_breaker_state` |
| Source Count | Gauge | 5 | `prism_sources_active` |

**Dashboard JSON structure:**

```json
{
  "dashboard": {
    "title": "Prism Pipeline",
    "uid": "prism-main",
    "tags": ["prism"],
    "timezone": "utc",
    "refresh": "30s",
    "time": { "from": "now-6h", "to": "now" },
    "panels": [...]
  }
}
```

Each panel references the Prometheus datasource and uses the
`prism_` prefixed metric names from 05_01/05_02.

---

## Directory Structure

```
monitoring/
  prometheus.yml
  provisioning/
    datasources/
      prometheus.yml
    dashboards/
      default.yml
  dashboards/
    prism.json
```

---

## Security Notes

- Prometheus UI (`9090`) and Grafana (`3001`) should be behind a
  reverse proxy or firewall in production — not exposed to the internet.
- Default Grafana password is `admin` — override with `GRAFANA_PASSWORD`
  env var in production.
- `/metrics` endpoint is public. It exposes operational counters, not
  user data. If this changes, add a dedicated metrics bearer token.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `docker compose up` starts prometheus + grafana | Verify containers running |
| 2 | Prometheus targets page shows "prism-api" as UP | Visit `http://localhost:9090/targets` |
| 3 | Prometheus can query `prism_discovery_articles_total` | Execute query in Prometheus UI |
| 4 | Grafana loads at port 3001 | Visit `http://localhost:3001` |
| 5 | Grafana datasource auto-configured | Settings → Data Sources → Prometheus exists |
| 6 | Dashboard "Prism Pipeline" auto-provisioned | Dashboards page shows it |
| 7 | All 8+ panels render without errors | Open dashboard, verify no "No data" |
| 8 | Prometheus retains 30 days of data | Check `--storage.tsdb.retention.time` flag |
| 9 | Grafana persists across restarts | Restart containers, verify dashboard intact |
| 10 | Named volumes for data persistence | Verify `prometheus_data` and `grafana_data` |

---

## Testing Strategy

```bash
# Smoke test: bring up stack, verify scraping
docker compose -f docker-compose.prod.yml up -d
sleep 10

# Prometheus scraping
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'
# Expected: "up"

# Grafana health
curl -s http://localhost:3001/api/health | jq '.database'
# Expected: "ok"

# Prometheus has prism metrics
curl -s 'http://localhost:9090/api/v1/query?query=prism_sources_active' \
  | jq '.data.result[0].value[1]'
# Expected: numeric value

# Dashboard exists
curl -s -u admin:admin http://localhost:3001/api/dashboards/uid/prism-main \
  | jq '.dashboard.title'
# Expected: "Prism Pipeline"
```

---

## Files Changed

| File | Change |
|------|--------|
| `docker-compose.prod.yml` | Add prometheus + grafana services, volumes |
| `monitoring/prometheus.yml` | New: scrape config |
| `monitoring/provisioning/datasources/prometheus.yml` | New: datasource |
| `monitoring/provisioning/dashboards/default.yml` | New: dashboard provider |
| `monitoring/dashboards/prism.json` | New: 8-panel dashboard |

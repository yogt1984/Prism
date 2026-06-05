# Architecture Scaling Proposal — June 5, 2026

## Current Architecture Strengths

What's already modular and well-positioned for scaling:

- **Agents are separate modules** with clear inputs/outputs (D_AI, A_AI, P_AI, W_AI, R_AI)
- **`resonance.py` and `perception.py` are pure functions** — no DB access, fully portable, can run anywhere
- **Database models are centralized** in `models.py` via SQLModel (ORM-portable to Postgres)
- **Config is injectable** via Pydantic Settings — environment-driven, no hardcoded values
- **API layer is stateless** — FastAPI with no server-side session state

## Current Coupling Points

Each of these works at current scale but creates a hard ceiling under load:

### SQLite
- Single-writer limitation means writes queue up under concurrent access
- WAL mode helps reads but doesn't solve write contention
- At ~1,000 concurrent API requests + agents writing simultaneously, responses stall
- **Fix:** Migrate to Postgres — can't be tuned past, must be replaced

### No Message Queue
- APScheduler runs agents in fixed sequence on timers (D_AI → A_AI → R_AI → P_AI+W_AI)
- If A_AI takes 45 minutes, the next 30-minute cycle fires anyway — potential double-processing
- No backpressure, no fan-out, no dead-letter queue
- Can't add a second A_AI worker because there's no queue to pull from
- **Fix:** Introduce task queue (Celery/Redis or Postgres-backed)

### Sync-Only Execution
- FastAPI routes call Claude API and Brave Search synchronously
- Each request holds a uvicorn worker hostage for 2–5 seconds
- With 4 workers (default), 5 concurrent briefing-generation requests = API unresponsive
- **Fix:** Async route handlers + `httpx.AsyncClient` + `anthropic.AsyncAnthropic`

### In-Process Metrics
- Metrics reset on every restart — no persistence across deploys
- No Prometheus export, no StatsD, no time-series storage
- Can't observe trends beyond a single process lifetime
- **Fix:** Prometheus exporter or external metrics service

## Horizontal Scaling Architecture

If/when horizontal scaling is needed, the target architecture:

```
                    Redis / Postgres Queue
                   /         |         \
              D_AI worker  A_AI worker  R_AI worker
              (box 1)      (box 2)      (box 1)
                   \         |         /
                      Postgres (shared)
                   /         |         \
              P_AI worker  W_AI worker  API servers
              (box 3)      (box 3)      (box 1,2,3)
```

Each agent becomes a stateless worker. Scale bottleneck agents independently (e.g., 3 A_AI workers if analysis is slow, 1 D_AI if discovery is fast). API layer goes behind a load balancer with N copies.

### Changes Required for Horizontal

| Change | Effort | Unlocks |
|---|---|---|
| SQLite → Postgres | Medium | Concurrent writes, multiple API servers |
| APScheduler → task queue | Medium | Independent agent scaling, backpressure |
| Sync → async | Large | Higher throughput per instance |
| Add Redis cache | Small | API read performance |

Postgres alone gets ~80% of the benefit — multiple API servers, concurrent agent writes, real connection pooling. Task queue is step two, only when multiple workers per agent type are needed.

## Recommendation: Vertical First

For Prism's current stage (pre-launch, beta users), **vertical scaling is the right first move**.

### Why Vertical Wins Now

- **Workload is I/O bound, not CPU bound.** Agents spend 90% of time waiting on Claude API, Brave API, and Resend. A bigger CPU won't help, but async on a single box will.
- **SQLite with WAL on NVMe handles ~50k reads/sec.** The bottleneck is external API calls, not the database.
- **A single $50/mo VPS** (4 cores, 8GB RAM) can serve thousands of users if the code is async.
- **Operational complexity stays near zero.** One box, one deploy, one log stream, one backup.

### Vertical Scaling Steps

1. Make agents async (`httpx.AsyncClient` for Brave/Resend, `anthropic.AsyncAnthropic` for Claude)
2. Run async FastAPI properly (async route handlers)
3. Add Redis for caching story listings and user profiles
4. Stay on SQLite until write contention is actually observed

This handles **thousands of daily users** on one machine.

### When to Go Horizontal

Horizontal scaling makes sense when:

- Processing 10k+ stories/cycle and A_AI can't keep up even with async
- Geographic redundancy needed (uptime SLA for paying customers)
- Zero-downtime deploys required

These are post-product-market-fit problems. Metrics will signal when you're there.

### The Trap to Avoid

Going horizontal too early means debugging distributed systems (network partitions, queue poisoning, split-brain) instead of improving briefing quality and acquiring users. Horizontal scaling is an **operations tax** — don't pay it until revenue justifies it.

## Summary

| Phase | Trigger | Action | Cost |
|---|---|---|---|
| **Now** | Current state | Ship, get users, validate product | $0 |
| **Phase 1** | API latency under load | Async agents + async FastAPI + Redis cache | ~1 week eng |
| **Phase 2** | Write contention observed | SQLite → Postgres | ~1 week eng |
| **Phase 3** | Single box maxed out | Task queue + horizontal workers | ~2–3 weeks eng |

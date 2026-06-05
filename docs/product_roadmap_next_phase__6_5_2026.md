# Prism — Product Roadmap: Post-MVP Next Phase

**Date:** 2026-06-05
**Status:** Proposal — pending prioritization

---

## Current State Assessment

Prism's backend is a **fully implemented MVP** with all core agents operational
and connected end-to-end. This document captures the current state and outlines
the next phase of development to transition from a working backend into a
user-facing product.

### What Is Built

| Component             | Status   | Summary                                                    |
|-----------------------|----------|------------------------------------------------------------|
| D_AI (Discovery)      | Complete | Brave Search + RSS, Jaccard/TF-IDF dedup, story clustering |
| A_AI (Analysis)       | Complete | Claude-powered multi-perspective analysis, quality checks   |
| R_AI (Perception)     | Complete | Keyword tracking, salience/valence, perception pressure     |
| P_AI (Personalization)| Complete | Interest scoring, tier enforcement, engagement feedback     |
| W_AI (Writer)         | Complete | Email/JSON/audio script generation, Resend delivery         |
| CLI                   | Complete | 11 command groups, 49+ subcommands                         |
| REST API              | Complete | 30+ endpoints, API-key auth, tier gating, OpenAPI docs     |
| Database              | Complete | SQLite WAL, 13 tables, Alembic migrations, backup          |
| Resonance Metric      | Complete | Media impact scoring, A_AI integration, API/CLI exposure   |
| Perception Tracking   | Complete | R_AI agent, keyword management, history snapshots          |
| Testing               | Complete | 882 tests across 43 files, full coverage                   |
| Docker / CI           | Complete | Multi-stage Dockerfile, prod compose, GitHub Actions       |
| Config                | Complete | Pydantic Settings, 20+ injectable parameters               |
| Monitoring / Alerts   | Complete | In-process metrics, ntfy.sh push notifications             |
| Circuit Breaker       | Complete | Graceful degradation for Brave/Claude/Resend               |
| Error Recovery        | Complete | Exponential backoff retry, transient error handling        |

### Pipeline Data Flow (Production-Ready)

```
D_AI (every 2h)
  Brave API + RSS feeds --> deduplicate --> StoryCluster (status=RAW)
        |
        v
A_AI (every 30m)
  RAW clusters --> Claude analysis --> perspectives + resonance --> (status=ANALYZED)
        |
        v
R_AI (every 30m)
  ANALYZED clusters --> keyword scan --> perception pressure snapshots
        |
        v
P_AI + W_AI (daily 7am UTC)
  Score stories per user --> select top N --> generate briefing --> deliver via email
        |
        v
  User engagement --> P_AI feedback loop
```

### Key Statistics

- **Source code:** ~3,600 lines in `src/prism/`
- **Test code:** ~13,350 lines, 882 tests
- **Database models:** 13 tables with full relationships
- **External integrations:** Claude (Anthropic), Brave News, Resend Email, ntfy.sh
- **Runtime dependencies:** 22 packages (anthropic, sqlmodel, fastapi, apscheduler, etc.)

---

## Identified Gaps

The backend is production-ready but there is **no user-facing interface** beyond
the CLI, **no payment flow** for the Pro tier, and **no audio synthesis** for the
audio briefing scripts W_AI already generates.

---

## Next Phase — Prioritized Features

### Priority 1: Web Frontend

**Impact:** Highest — transforms backend into a usable product.

The REST API is fully built. What's missing is a user-facing web interface.

**Scope:**

- **Briefing reader** — render W_AI's HTML briefings with perspective toggles
  and source attribution links
- **Keyword/perception dashboard** — visualize R_AI's perception pressure charts
  over time (the data already exists via API)
- **User preferences panel** — manage interests, briefing format, frequency
  (P_AI supports all of this through existing endpoints)
- **Source transparency view** — display trust scores and bias labels per source,
  making bias visible (core product differentiator)
- **Story explorer** — browse analyzed clusters sorted by resonance, category,
  or recency

**Suggested stack:** Next.js + Tailwind CSS, hitting existing FastAPI endpoints.
Deploy alongside the backend on existing infrastructure.

**Why first:** Every other improvement is incremental backend enhancement. The
frontend is what makes Prism accessible to non-technical users and enables
subscription revenue.

---

### Priority 2: Stripe Payment Integration

**Impact:** High — enables the revenue model.

Pro tier ($7/mo) is already enforced in code:

- P_AI limits free users to 1 interest category, max 10 stories
- W_AI restricts free users to email-only format
- API endpoints gate Pro-only features

**What's missing:** Actual payment processing.

**Scope:**

- Stripe Checkout session creation for Pro upgrade
- Webhook handler to flip `user.tier` on successful payment
- Subscription management (cancel, reactivate) via Stripe Customer Portal
- Grace period handling for failed payments

---

### Priority 3: TTS Audio Briefings

**Impact:** Medium — Pro-tier differentiator.

W_AI already generates audio briefing scripts with phonetic guidance for proper
nouns. The missing piece is actual speech synthesis.

**Scope:**

- Integrate OpenAI TTS or ElevenLabs API
- Convert W_AI audio scripts to playable audio files (MP3)
- Store and serve audio via API endpoint
- Add playback to the web frontend

---

### Priority 4: Async FastAPI + WebSocket Support

**Impact:** Medium — scaling and UX improvement.

The architecture proposal (`docs/architecture_proposal__5_6_2026.md`) identifies
sync FastAPI as a bottleneck. Migrating to async enables:

- **WebSocket push** for live briefing delivery and perception updates
- **Better concurrency** under multiple simultaneous users
- **Non-blocking I/O** for Claude and Brave API calls in the request path

**Scope:**

- Convert sync endpoint handlers to `async def`
- Add WebSocket endpoints for real-time dashboard updates
- Async database session management (SQLAlchemy async engine)

---

### Priority 5: Prometheus Metrics Export

**Impact:** Medium — operational visibility.

`src/prism/metrics.py` tracks counters in-process but does not expose them
externally.

**Scope:**

- Add `/metrics` endpoint in Prometheus exposition format
- Export existing counters: discovery cycles, analysis runs, briefings sent,
  API latency histograms, circuit breaker state
- Grafana dashboard templates for pipeline health monitoring
- Alert rules for degraded pipeline states

---

### Priority 6: Source Auto-Discovery

**Impact:** Medium-long term — compounds platform value.

Currently limited to 30 seeded sources plus manual CLI addition. D_AI could
autonomously expand coverage.

**Scope:**

- **Candidate pipeline:** D_AI discovers new sources via Brave during regular
  search cycles
- **Probation period:** New sources start with `trust_score=0.0` and
  `status=CANDIDATE`
- **Automated promotion:** After N articles successfully cross-referenced against
  trusted sources, promote to active with earned trust score
- **Quality gate:** Sources that repeatedly fail fact-checking or produce
  low-quality clusters get demoted automatically

---

## Recommended Execution Order

```
Phase 1 (Foundation)     Phase 2 (Revenue)        Phase 3 (Scale)
─────────────────────    ─────────────────────     ─────────────────────
Web Frontend             Stripe Integration        Async FastAPI
                         TTS Audio                 Prometheus Export
                                                   Source Auto-Discovery
```

Phase 1 is the prerequisite for Phase 2 — payment integration needs a web UI
for the checkout flow. Phase 3 items are independent and can be tackled in any
order based on observed bottlenecks.

---

## Production Readiness Notes

Carried forward from the architecture proposal:

| Aspect          | Current Status                        | Next Phase Target             |
|-----------------|---------------------------------------|-------------------------------|
| Core pipeline   | Production-ready, fully tested        | No changes needed             |
| Error handling  | Retry + circuit breaker               | No changes needed             |
| Database        | SQLite WAL, migrations, backup        | Evaluate Postgres at scale    |
| API security    | API key hashing, auth, tier gating    | Add OAuth for frontend auth   |
| Scalability     | Single-box vertical only              | Async + optional task queue   |
| Monitoring      | In-process counters, ntfy.sh alerts   | Prometheus + Grafana          |
| Deployment      | Docker, compose, CI                   | Add frontend build to CI      |

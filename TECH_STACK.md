# Tech Stack — Prism

Chosen for: low technical debt, minimal infrastructure cost, fast iteration.

## Language & Runtime

- **Python 3.12+** — single language across all agents

## Core Services

| Component | Tool | Why |
|-----------|------|-----|
| LLM | Claude API (Anthropic SDK) | Summarization, analysis, perspective detection, briefing writing |
| News discovery | Brave Search API | Privacy-respecting, good news index, affordable ($5/mo for 2k queries) |
| RSS fallback | `feedparser` | Supplement Brave with direct RSS from trusted sources |
| Message queue | Redis Streams | Lightweight inter-agent messaging |
| Database | SQLite (via SQLModel) | Stories, users, profiles, engagement — zero ops |
| Email delivery | Resend ($0/mo free tier, 100 emails/day) | Transactional email for briefings |
| Scheduling | APScheduler | Periodic discovery, briefing generation |

## Agent-Specific

### D_AI — Discovery
| Component | Tool | Why |
|-----------|------|-----|
| Search | Brave Search API (`brave-search` Python client) | News-focused search with freshness controls |
| RSS | `feedparser` | Direct feed monitoring for high-trust sources |
| Dedup | MinHash / SimHash (via `datasketch`) | Detect same story across outlets |
| Source registry | SQLite table | Trust scores, bias labels, category tags |

### A_AI — Analysis
| Component | Tool | Why |
|-----------|------|-----|
| Summarization | Claude API (structured output) | Multi-perspective summaries with JSON schema |
| Categorization | Claude API | Topic tagging, sentiment, framing analysis |
| Fact extraction | Claude API | Key claims with source attribution |

### P_AI — Personalization
| Component | Tool | Why |
|-----------|------|-----|
| User profiles | SQLite | Interest vectors, preferences, history |
| Ranking | Simple weighted scoring | No ML needed initially — interest match + recency + source diversity |
| Engagement tracking | SQLite | Opens, read-time, saves |

### W_AI — Writer
| Component | Tool | Why |
|-----------|------|-----|
| Briefing generation | Claude API | Final editorial pass with consistent voice |
| Email rendering | `mjml` or Jinja2 templates | Responsive HTML emails |
| Audio (future) | ElevenLabs or Coqui TTS | Audio briefing delivery |

## Infrastructure

| Layer | Choice | Why |
|-------|--------|-----|
| Compute | Single VPS (Hetzner CX32, ~$15/mo) | All agents on one box |
| DB | SQLite | Zero-ops, sufficient for first 10k users |
| Queue | Redis (same box) | Inter-agent messaging |
| Email | Resend (free → $20/mo at scale) | Simple API, good deliverability |
| Web API (future) | FastAPI | When adding web/app feed |
| Monitoring | Logging + ntfy.sh | Free push notifications on failures |
| CI/CD | GitHub Actions | Lint + test on push |

## Cost Estimate (Monthly, MVP Phase)

| Item | Cost |
|------|------|
| VPS (Hetzner) | $15 |
| Claude API (summarization + analysis) | $30-80 |
| Brave Search API (Base plan) | $5 |
| Resend (email) | $0 (free tier) |
| **Total** | **~$50-100/mo** |

## What to Avoid

- **No vector DB** — not doing semantic search, simple keyword/category matching suffices
- **No Elasticsearch** — SQLite FTS5 handles full-text search at this scale
- **No ML recommendation engine** — weighted scoring with explicit preferences beats collaborative filtering when you have <10k users
- **No frontend framework yet** — email-first, add web UI only when validated
- **No Kubernetes** — single box

## Migration Path

- SQLite → PostgreSQL when concurrent writes matter (~5k+ active users)
- Resend → SendGrid/SES when volume exceeds free tier
- Add FastAPI + simple React frontend when email-only feels limiting
- Add TTS pipeline when audio briefings are validated

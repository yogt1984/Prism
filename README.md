```


                                          .
                                         /|\
                                        / | \
                                       /  |  \
                                      /   |   \
                                     /    |    \
                                    / .---+---. \
                                   / /  R   G  \ \
                                  / /     |     \ \
                                 / /  B   |   Y  \ \
                                / /       |       \ \
                               / /   _____|_____   \ \
                              / /   /     |     \   \ \
                             / /   /      |      \   \ \
                            / /   /  _____|_____  \   \ \
                           / /   /  /     |     \  \   \ \
                          / /   /  /      |      \  \   \ \
                         /./   /  /       |       \  \   \.\
                       .+----./  /        |        \  \.----+.
                      / |       /         |         \       | \
                     /  |      /__________|__________\      |  \
                    /   |     /===========|===========\     |   \
                   /    |    /            |            \    |    \
                  /     |   /             |             \   |     \
                 /      |  /     P R I S M              \  |      \
                /       | /   multi-perspective          \ |       \
               /        |/     news briefings             \|        \
              /=========|==================================|=========\
             /     _____|_____          |          _____|_____        \
            /     /     |     \         |         /     |     \       \
           /     /      |      \        |        /      |      \      \
          /     /  bias |shown  \       |       / every | claim  \     \
         /     /   not  |hidden  \      |      /  links | back    \     \
        /     /         |         \     |     /    to   | source   \     \
       /_____/__________|__________\____|____/__________|__________\_____\
              ░▒▓ DISCOVER ▓▒░   ░▒▓ ANALYZE ▓▒░   ░▒▓ DELIVER ▓▒░

          "Humans cannot be objective -- neither can AI.
                   We make the bias transparent."

```

Prism is an AI-powered news curation platform. It discovers trending stories from
trusted sources, analyzes them through multiple editorial perspectives, and
delivers personalized daily briefings where every claim is attributed to its
origin. Bias is shown, not hidden.

---

## Pipeline

```
  D_AI          A_AI           R_AI            P_AI          W_AI
discover  -->  analyze  -->  perception  -->  personalize  -->  deliver
 (Brave)      (Claude)      (keywords)       (scoring)      (Resend)
  + RSS       sentiment      salience         interests      email
              bias labels    valence           resonance      briefing
                             momentum          perception
```

Five agents communicate via a DB state machine (`RAW -> ANALYZED -> delivered`).
No message queue, no Redis -- just SQLite in WAL mode.

---

## Resonance -- Media Impact Score

Resonance is Prism's core metric for measuring how much media attention a topic
commands. Every story cluster gets a continuously updated score:

```
Resonance = breadth(sources) x Sigma( trust x engagement x decay )
```

| Component | What it measures |
|-----------|-----------------|
| **Trust** | Source authority from the registry -- Reuters >> unknown blog |
| **Engagement** | Log-scaled audience reactions, normalized per platform |
| **Breadth** | Source diversity -- penalizes single-outlet repetition |
| **Decay** | Exponential (24h half-life) -- stale stories fade naturally |

Derived signals track how stories evolve: **Momentum** (rising or fading),
**Peak Resonance** (historical max), and **Persistence** (how long a story
stays above threshold).

Resonance feeds directly into personalized story ranking -- high-resonance
stories bubble up in briefings while still respecting user interests.

```bash
prism resonance                        # top stories by media impact
prism resonance --keyword "tariff"     # resonance for a specific topic
prism resonance show 42                # full breakdown for a story
```

```
GET /stories?sort=resonance            # API: stories ranked by resonance
GET /stories/42/resonance              # API: full score breakdown
```

See [docs/resonance_specs.md](docs/resonance_specs.md) for the full formula,
parameters, and implementation details.

---

## Perception Pressure -- Media Perception Tracking

Perception Pressure is Prism's longitudinal metric for tracking **how the media
shapes public perception of a keyword or concept over time**. Unlike Resonance
(which scores a single story cluster), Perception tracks a keyword *across all
stories* and produces a signed float that evolves with every analysis cycle.

```
P(K,t) = salience(K,t) x valence(K,t)
```

```
                     P(K,t) Perception Pressure
                          ^
                          |
              +3.5  ......|...........*............  <-- strong positive framing
                          |        *    *
              +1.0  ......|......*.........*........  <-- mild positive lean
                          |    *              *
               0.0  ------+--*------------------*---  <-- balanced or no coverage
                          |                      *
              -1.5  ......|........................*  <-- negative shift begins
                          |
                          +------------------------> time
                         t0   t1   t2   t3   t4
```

| Component | Definition | Range |
|-----------|-----------|-------|
| **Salience** A(K,t) | Total media attention: `Sigma[ breadth x decay ]` across matching clusters | 0 to +inf |
| **Valence** V(K,t) | Trust-weighted average sentiment across all perspectives | -1.0 to +1.0 |
| **Perception** P(K,t) | `A x V` -- net media pressure, the single signed float | -inf to +inf |
| **Momentum** dP/dt | Rate of change vs previous snapshot | unbounded |

**Reading the signal:**

| Value | Interpretation |
|-------|---------------|
| `P > 0` | Net positive media framing |
| `P < 0` | Net negative media framing |
| `\|P\| large` | Strong, broad, authoritative, fresh coverage |
| `\|P\| ~ 0` | Either nobody's covering it, or coverage is perfectly balanced |
| `dP/dt > 0` | Perception shifting positive (narrative building) |
| `dP/dt < 0` | Perception shifting negative (backlash forming) |

**Track keywords and monitor perception:**

```bash
prism perception keyword add "tariff" --aliases "tariffs,trade barriers"
prism perception keyword add "AI regulation" --category tech
prism perception keyword ls               # list tracked keywords
prism perception                           # latest scores for all keywords
prism perception show 1 --history 20       # detail + history for keyword
prism perception scan                      # manual trigger
```

```
GET  /keywords                             # list tracked keywords
POST /keywords                             # add a keyword to track
GET  /keywords/1/perception                # latest perception snapshot
GET  /keywords/1/perception/history        # time series
DELETE /keywords/1                         # deactivate keyword
```

The R_AI agent (Resonance Tracker) runs on the same 30-minute schedule as
analysis, scanning all analyzed clusters for tracked keywords and computing
fresh perception snapshots.

---

## Quick Start

### With Docker (recommended)

```bash
cp deploy/env.production.example .env   # fill in API keys
docker compose build
docker compose run --rm prism prism db init
docker compose run --rm prism prism source seed
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

See [docs/deployment.md](docs/deployment.md) for the full deployment guide.

### With pip

```bash
pip install -e ".[dev]"
cp .env.example .env       # fill in API keys
prism config check         # verify connectivity
prism source seed          # load 30 curated sources
prism run --once           # single discovery -> analysis -> briefing cycle
```

## REST API

Prism exposes a FastAPI-based REST API for programmatic access. Run with
`uvicorn prism.api.app:create_app --factory` or import `create_app()`.

**Public endpoints** (no auth):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/config` | Non-secret runtime configuration, categories, tier limits |
| GET | `/sources` | List sources (`?active=true/false` filter) |
| GET | `/stories` | List stories (`?status=`, `?sort=resonance`, `?limit=`, `?offset=`) |
| GET | `/stories/{id}` | Story detail with articles + perspectives |
| GET | `/stories/{id}/resonance` | Full resonance score breakdown |
| GET | `/keywords` | List tracked keywords (`?active=` filter) |
| POST | `/keywords` | Add a keyword to track |
| GET | `/keywords/{id}/perception` | Latest perception snapshot |
| GET | `/keywords/{id}/perception/history` | Perception time series |
| DELETE | `/keywords/{id}` | Deactivate a tracked keyword |
| POST | `/users` | Register a new user |

**Authenticated endpoints** (require `X-API-Key` header, Pro tier):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/{id}` | Get user profile |
| PATCH | `/users/{id}` | Update interests, format, depth, name |
| GET | `/users/{id}/briefings` | List briefings (paginated) |
| GET | `/users/{id}/briefings/{bid}` | Briefing detail with content |
| POST | `/users/{id}/briefings` | Trigger on-demand briefing |
| POST | `/engagements` | Record interaction (open/read/save/skip) |
| POST | `/users/{id}/checkout` | Create Stripe checkout session |
| POST | `/users/{id}/portal` | Create Stripe customer portal session |
| POST | `/webhooks/stripe` | Stripe webhook handler (checkout, invoice, cancellation) |

Interactive docs at `/docs` (Swagger UI) and `/redoc`.

## CLI

Prism ships a full terminal control plane. Install with `pip install -e .` and
run `prism --help` to explore.

```
prism resonance [--keyword] [--sort]  top stories by media impact
prism resonance show <id>             full resonance breakdown
prism perception                      latest perception for all keywords
prism perception show <id>            perception detail + history
prism perception keyword add|ls|rm    manage tracked keywords
prism perception scan                 manual perception cycle
prism run [--once]           start scheduler or single cycle
prism status [--watch]       live pipeline dashboard
prism cycle discover|analyze|brief   trigger individual agents
prism user   add|ls|show|edit|rm     manage subscribers
prism source ls|add|seed|trust|bias  source registry
prism story  ls|show|stats           inspect story clusters
prism briefing ls|show|preview|resend  briefing management
prism config show|check|env          configuration & health
prism db     init|stats|export       database management
prism docs   spec|cli|roadmap|...    in-terminal doc viewer
```

Global flags: `--json` (machine-readable output), `--quiet` / `-q` (suppress
progress messages), `--db <url>` (override database).

## Configuration

| Variable | Required | Default |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | -- |
| `BRAVE_API_KEY` | No | `""` |
| `RESEND_API_KEY` | No | `""` |
| `DATABASE_URL` | No | `sqlite:///data/newsgen.db` |
| `DISCOVERY_INTERVAL_HOURS` | No | `2` |
| `MAX_STORIES_PER_CYCLE` | No | `50` |
| `DEFAULT_BRIEFING_STORIES` | No | `10` |
| `RESONANCE_HALF_LIFE_HOURS` | No | `24` |
| `RESONANCE_WINDOW_HOURS` | No | `72` |
| `RESONANCE_RANKING_WEIGHT` | No | `0.3` |
| `PERCEPTION_HALF_LIFE_HOURS` | No | `24` |
| `PERCEPTION_WINDOW_HOURS` | No | `72` |
| `PERCEPTION_SCAN_INTERVAL_MINUTES` | No | `30` |
| `STRIPE_SECRET_KEY` | No | `""` |
| `STRIPE_PRICE_ID` | No | `""` |
| `STRIPE_WEBHOOK_SECRET` | No | `""` |
| `GRACE_PERIOD_DAYS` | No | `7` |

## Testing

```bash
pytest                                   # 880+ backend tests
ruff check src/ tests/                   # backend lint
cd frontend && npx vitest run            # 1058 frontend tests
```

## Project Structure

```
src/prism/
  main.py        scheduler orchestration (APScheduler)
  config.py      settings via pydantic-settings
  db.py          SQLite + WAL mode
  models.py      Source, StoryCluster, Article, Perspective, User, Briefing,
                 TopicResonance, KeywordTrack, KeywordMention, PerceptionSnapshot
  retry.py       exponential backoff for transient API failures
  alerts.py      ntfy.sh notification forwarding
  resonance.py   topic media impact score computation
  perception.py  perception pressure computation (salience x valence)
  onboarding.py  user registration with email/interest validation
  seed.py        30 curated sources across the bias spectrum
  agents/
    d_ai.py      discovery: Brave API + RSS + Jaccard dedup
    a_ai.py      analysis: Claude structured output + token budget + resonance
    r_ai.py      perception: keyword scanning + perception pressure computation
    p_ai.py      personalization: scoring + story selection + resonance ranking
    w_ai.py      writer: briefing generation + email delivery
  api/
    app.py       FastAPI application factory
    routes.py    REST endpoints, auth, Pydantic schemas
  cli/
    app.py       root typer app, global flags, subcommand registry
    _fmt.py      shared formatting: JSON/quiet modes, table/info helpers
    resonance.py top-level resonance query (--keyword, show)
    perception.py keyword tracking + perception query + manual scan
    run.py       scheduler start / single cycle
    status.py    live Rich dashboard
    cycle.py     manual agent triggers
    user.py      subscriber CRUD
    source.py    source registry management
    story.py     cluster inspection + stats
    briefing.py  briefing listing, preview, resend
    config_cmd.py  config display + health checks
    db_cmd.py    database init, stats, export
    docs.py      in-terminal markdown viewer + search
docs/
  specifications.md    full system requirements (agents, data model, reliability)
  resonance_specs.md   resonance metric definition, formula, implementation tasks
  cli-specification.md CLI command tree, output examples, milestones
frontend/
  app/               Next.js App Router pages (12 routes)
  components/        React components by domain (dashboard, story, briefing,
                     sources, perception, settings, subscription, navigation, ui)
  lib/               types.ts, hooks.ts (25 data-fetching hooks), api.ts
  __tests__/         87 test files, 1058 tests (vitest + testing-library)
```

## Web Frontend

Next.js + Tailwind CSS application consuming the REST API via a BFF proxy.

**Pages:**

| Route | Description |
|-------|-------------|
| `/` | Product landing page -- value props, how-it-works, CTAs |
| `/login`, `/signup` | Authentication (next-auth) |
| `/dashboard` | Story feed with top stories, resonance badges, keyword sidebar |
| `/stories/{id}` | Story detail with multi-perspective viewer, engagement tracking |
| `/briefings` | Briefing list with pagination, format/sent badges |
| `/briefings/{id}` | Briefing reader (HTML/plaintext) with engagement tracking |
| `/sources` | Source explorer -- trust scores, bias labels, lifecycle status filters |
| `/perception` | Perception dashboard -- keyword charts, sparklines, momentum |
| `/settings` | Profile, interests, briefing preferences, subscription management |
| `/pricing` | Free vs Pro tier comparison with contextual upgrade CTAs |

**Key features:**

- **Engagement feedback loop**: Story detail and briefing reader record open/read/save/skip
  events, closing the P_AI personalization loop
- **Source lifecycle UI**: Surfaces D_AI discovery status (seed → candidate → probation →
  trusted/rejected) with status badges and filter chips
- **Subscription flow**: Stripe checkout integration, grace period handling, upgrade/manage CTAs
- **Shared UI components**: Button, Card, Skeleton, Badge primitives used across all pages
- **Responsive navigation**: Sidebar on desktop (lg+), bottom nav on mobile/tablet
- **1058 frontend tests** across 87 test files (vitest + testing-library)

```bash
cd frontend && npm install && npm run dev   # development server on :3000
npx vitest run                              # run test suite
```

---

## Development Status

**Completed milestones:**

- **M0**: Foundation -- database, config, CI
- **M1-M6**: Core pipeline -- all four agents (D_AI, A_AI, P_AI, W_AI),
  data model, scheduling, retry/alerting, user onboarding, source seeding
- **M7**: CLI terminal control plane (`prism` command) -- scaffold, data
  commands, operations, docs viewer, global flags polish
- **M8**: Agent hardening & spec compliance -- RSS date fix, Brave
  `published_at` parsing, `max_stories_per_cycle`, trust-based sort,
  engagement test coverage, feedback loop, format skip logging, E2E tests
- **M9**: Tier limits & configuration -- cross-cycle title merge, free/pro
  tier enforcement, cron schedule wiring, max perspectives cap, zero-result
  alerts, Brave source name extraction, enum cleanup
- **M10**: REST API -- FastAPI scaffold, public read endpoints (sources,
  stories), user CRUD, briefing list/detail/trigger, engagement recording,
  API key auth with pro-tier gating, OpenAPI docs, E2E integration tests,
  `prism db` CLI commands
- **Resonance**: Topic media impact score -- composite metric (trust x
  engagement x breadth x decay), A_AI integration, API/CLI exposure,
  P_AI ranking boost, 39 new tests
- **Perception Pressure**: Longitudinal keyword tracking -- R_AI agent,
  signed perception float (salience x valence), keyword management,
  time-series snapshots, momentum tracking, CLI + API exposure, 24 new tests
- **Source Auto-Discovery**: D_AI candidate pipeline -- automated source
  discovery via Brave, probation lifecycle (seed → candidate → probation →
  trusted/rejected), quality gates, trust promotion
- **Web Frontend**: Next.js application -- 12 routes, engagement tracking,
  source lifecycle UI, subscription flow, pricing page, landing page,
  shared UI components, responsive navigation, 1058 tests

## Tech Stack

**Backend:** Python 3.12 / SQLModel / Claude API / Brave Search / Resend /
APScheduler / FastAPI / Uvicorn / Typer / Rich / SQLite WAL

**Frontend:** Next.js / React / TypeScript / Tailwind CSS / TanStack Query /
next-auth / vitest / testing-library

## License

Proprietary. All rights reserved.

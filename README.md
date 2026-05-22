```

  ██████╗ ██████╗ ██╗███████╗███╗   ███╗
  ██╔══██╗██╔══██╗██║██╔════╝████╗ ████║
  ██████╔╝██████╔╝██║███████╗██╔████╔██║
  ██╔═══╝ ██╔══██╗██║╚════██║██║╚██╔╝██║
  ██║     ██║  ██║██║███████║██║ ╚═╝ ██║
  ╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝
       ░▒▓ multi-perspective news briefings ▓▒░

```

Prism is an AI-powered news curation platform. It discovers trending stories from
trusted sources, analyzes them through multiple editorial perspectives, and
delivers personalized daily briefings where every claim is attributed to its
origin. Bias is shown, not hidden.

*"Humans cannot be objective -- neither can AI. We make the bias transparent."*

---

## Pipeline

```
  D_AI          A_AI           P_AI          W_AI
discover  -->  analyze  -->  personalize  -->  deliver
 (Brave)      (Claude)       (scoring)      (Resend)
  + RSS       sentiment       interests      email
              bias labels     history        briefing
```

Four agents communicate via a DB state machine (`RAW -> ANALYZED -> delivered`).
No message queue, no Redis -- just SQLite in WAL mode.

## Quick Start

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
| GET | `/stories` | List stories (`?status=`, `?limit=`, `?offset=`) |
| GET | `/stories/{id}` | Story detail with articles + perspectives |
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

Interactive docs at `/docs` (Swagger UI) and `/redoc`.

## CLI

Prism ships a full terminal control plane. Install with `pip install -e .` and
run `prism --help` to explore.

```
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

## Testing

```bash
pytest                       # 495 tests
ruff check src/ tests/       # lint
```

## Project Structure

```
src/prism/
  main.py        scheduler orchestration (APScheduler)
  config.py      settings via pydantic-settings
  db.py          SQLite + WAL mode
  models.py      Source, StoryCluster, Article, Perspective, User, Briefing
  retry.py       exponential backoff for transient API failures
  alerts.py      ntfy.sh notification forwarding
  onboarding.py  user registration with email/interest validation
  seed.py        30 curated sources across the bias spectrum
  agents/
    d_ai.py      discovery: Brave API + RSS + Jaccard dedup
    a_ai.py      analysis: Claude structured output + token budget
    p_ai.py      personalization: scoring + story selection
    w_ai.py      writer: briefing generation + email delivery
  api/
    app.py       FastAPI application factory
    routes.py    REST endpoints, auth, Pydantic schemas
  cli/
    app.py       root typer app, global flags, subcommand registry
    _fmt.py      shared formatting: JSON/quiet modes, table/info helpers
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
  cli-specification.md CLI command tree, output examples, milestones
```

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

## Tech Stack

Python 3.12 / SQLModel / Claude API / Brave Search / Resend / APScheduler /
FastAPI / Uvicorn / Typer / Rich / SQLite WAL

## License

Proprietary. All rights reserved.

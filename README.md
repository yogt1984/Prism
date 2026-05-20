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
pytest                       # 267 tests
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
  seed.py        30 curated sources across the bias spectrum
  agents/
    d_ai.py      discovery: Brave API + RSS + Jaccard dedup
    a_ai.py      analysis: Claude structured output + token budget
    p_ai.py      personalization: scoring + story selection
    w_ai.py      writer: briefing generation + email delivery
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
    docs.py      in-terminal markdown viewer + search
docs/
  specifications.md    full system requirements (agents, data model, reliability)
  cli-specification.md CLI command tree, output examples, milestones
```

## Development Status

**Completed milestones:**

- **M1-M6**: Core pipeline -- all four agents (D_AI, A_AI, P_AI, W_AI),
  data model, scheduling, retry/alerting, user onboarding, source seeding
- **M7**: CLI terminal control plane (`prism` command) -- scaffold, data
  commands, operations, docs viewer, global flags polish
- **M8** (in progress): Agent hardening & spec compliance
  - T8.1: Fix RSS `published_at` data loss
  - T8.2: Parse Brave API `published_at` from age field
  - T8.3: Enforce `max_stories_per_cycle` limit
  - T8.4: Sort articles by source trust score (not source_id)
  - T8.5: Engagement recording test coverage
  - T8.6: Close feedback loop (engagement after briefing) -- next
  - T8.7: Log non-email format skips
  - T8.8: E2E integration tests (trust sort + no-repeat verification)

## Tech Stack

Python 3.12 / SQLModel / Claude API / Brave Search / Resend / APScheduler /
Typer / Rich / SQLite WAL

## License

Proprietary. All rights reserved.

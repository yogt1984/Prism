# Prism

**AI-curated multi-perspective news briefings.**

Prism aggregates news from trusted sources, analyzes stories through multiple perspectives, and delivers personalized daily briefings with full source attribution. Every claim traces back to its origin — bias is shown, not hidden.

*"Humans cannot be objective. We make the bias transparent."*

## How It Works

Four AI agents operate as a pipeline, communicating via a DB state machine:

```
D_AI (discover) -> A_AI (analyze) -> P_AI (personalize) -> W_AI (deliver)
```

| Agent | Role |
|-------|------|
| **D_AI** | Discovers news via Brave Search API + RSS feeds, deduplicates into story clusters |
| **A_AI** | Analyzes clusters with Claude — extracts perspectives, sentiment, bias labels |
| **P_AI** | Scores and selects stories per user based on interests and reading history |
| **W_AI** | Generates attributed briefings and delivers via email (Resend) |

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd Prism
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, BRAVE_API_KEY, RESEND_API_KEY

# Seed sources and run
python -c "from prism.db import init_db; from prism.seed import seed_sources; e = init_db(); seed_sources(e)"
python -m prism.main
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `BRAVE_API_KEY` | No | `""` | Brave Search API key |
| `RESEND_API_KEY` | No | `""` | Resend email delivery key |
| `DATABASE_URL` | No | `sqlite:///data/newsgen.db` | SQLite database path |
| `BRIEFING_FROM_EMAIL` | No | `briefing@yourdomain.com` | Sender email address |
| `DISCOVERY_INTERVAL_HOURS` | No | `2` | Hours between discovery cycles |
| `DEFAULT_BRIEFING_STORIES` | No | `10` | Stories per briefing |

## Schedule

| Job | Frequency | Trigger |
|-----|-----------|---------|
| Discovery | Every 2 hours | Interval |
| Analysis | Every 30 minutes | Interval |
| Briefing | Daily at 7 AM | Cron |

## Testing

```bash
# Full suite (104 tests)
pytest

# Single module
pytest tests/test_e2e.py -v

# With linting
ruff check src/ tests/
```

## Project Structure

```
src/prism/
  main.py          # Scheduler orchestration (APScheduler)
  config.py        # Settings via pydantic-settings
  db.py            # SQLite + WAL mode + engine management
  models.py        # SQLModel tables (Source, StoryCluster, Article, Perspective, User, Briefing)
  seed.py          # 30 curated news sources across the bias spectrum
  agents/
    d_ai.py        # Discovery: Brave API + RSS + Jaccard dedup
    a_ai.py        # Analysis: Claude structured output + token budget
    p_ai.py        # Personalization: scoring + story selection
    w_ai.py        # Writer: briefing generation + email delivery
tests/
  test_db.py       # DB init, WAL, FK integrity, CRUD
  test_config.py   # Settings loading and validation
  test_discovery.py # Brave API, RSS, dedup, cross-cycle merge
  test_analysis.py  # Token truncation, cluster analysis, perspectives
  test_briefing.py  # Scoring, selection, generation, email, storage
  test_scheduler.py # Job registration, intervals, shutdown
  test_e2e.py       # Full pipeline integration tests
```

## Tech Stack

- **Python 3.12+** with SQLModel, Pydantic, APScheduler
- **Claude** (Anthropic API) for analysis and briefing generation
- **Brave Search API** for news discovery
- **SQLite** (WAL mode) for storage — no external DB needed
- **Resend** for email delivery

## License

Proprietary. All rights reserved.

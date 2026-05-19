```

  ██████╗ ██████╗ ██╗███████╗███╗   ███╗
  ██╔══██╗██╔══██╗██║██╔════╝████╗ ████║
  ██████╔╝██████╔╝██║███████╗██╔████╔██║
  ██╔═══╝ ██╔══██╗██║╚════██║██║╚██╔╝██║
  ██║     ██║  ██║██║███████║██║ ╚═╝ ██║
  ╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝
       ░▒▓ multi-perspective news briefings ▓▒░

```

Prism is an AI-only news curation platform. It discovers trending stories from
trusted sources, analyzes them through multiple editorial perspectives, and
delivers personalized daily briefings where every claim is attributed to its
origin. Bias is shown, not hidden.

*"Humans cannot be objective. We make the bias transparent."*

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
No message queue, no Redis — just SQLite in WAL mode.

## Quick Start

```bash
pip install -e ".[dev]"
cp .env.example .env       # fill in API keys
python -c "from prism.db import init_db; from prism.seed import seed_sources; e = init_db(); seed_sources(e)"
python -m prism.main
```

## Configuration

| Variable | Required | Default |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | — |
| `BRAVE_API_KEY` | No | `""` |
| `RESEND_API_KEY` | No | `""` |
| `DATABASE_URL` | No | `sqlite:///data/newsgen.db` |
| `DISCOVERY_INTERVAL_HOURS` | No | `2` |
| `DEFAULT_BRIEFING_STORIES` | No | `10` |

## Testing

```bash
pytest                       # 104 tests
ruff check src/ tests/       # lint
```

## Project Structure

```
src/prism/
  main.py        scheduler orchestration (APScheduler)
  config.py      settings via pydantic-settings
  db.py          SQLite + WAL mode
  models.py      Source, StoryCluster, Article, Perspective, User, Briefing
  seed.py        30 curated sources across the bias spectrum
  agents/
    d_ai.py      discovery: Brave API + RSS + Jaccard dedup
    a_ai.py      analysis: Claude structured output + token budget
    p_ai.py      personalization: scoring + story selection
    w_ai.py      writer: briefing generation + email delivery
```

## Tech Stack

Python 3.12 / SQLModel / Claude API / Brave Search / Resend / APScheduler / SQLite WAL

## License

Proprietary. All rights reserved.

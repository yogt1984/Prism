# Prism CLI — Client Tool Specification

> Single terminal entrypoint to manage, monitor, and inspect the entire Prism
> pipeline. Operators never need to leave the terminal.

---

## Design Principles

| Principle | Rationale |
|-----------|-----------|
| Single binary entrypoint: `prism` | One tool to rule the whole system |
| Subcommand tree (like `git`, `kubectl`) | Discoverable, scriptable |
| Rich terminal output (tables, panels, color) | Operator-friendly monitoring |
| JSON output mode on every command (`--json`) | Pipeable to `jq`, automation-friendly |
| No daemon — talks directly to SQLite + APIs | Zero infrastructure beyond what exists |
| Built-in docs viewer with search | Never leave the terminal to find specs |

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| CLI framework | **typer** (>= 0.12.0) | Type hints = CLI args, auto-help, click-compatible |
| Terminal rendering | **rich** (>= 13.0.0) | Tables, panels, live dashboards, markdown rendering, syntax highlighting |
| Entrypoint | `pyproject.toml [project.scripts]` | `pip install -e .` gives you `prism` globally |

---

## Command Tree

```
prism
│
├── run                              # Start the scheduler (wraps existing main.py)
│   ├── --once                       # Run one full cycle and exit
│   └── --dry-run                    # Simulate without API calls or DB writes
│
├── status                           # Live dashboard (refreshes every 5s)
│   │                                # Shows: last cycle times, cluster counts by status,
│   │                                # user count, pending briefings, API health
│   └── --watch                      # Continuous refresh (default: one-shot)
│
├── cycle                            # Manual trigger for individual agent cycles
│   ├── discover                     # Run D_AI discovery once
│   ├── analyze                      # Run A_AI analysis once
│   └── brief                        # Run P_AI + W_AI briefing once
│       └── --user <email>           # Single-user briefing (skip others)
│
├── user                             # User management
│   ├── add <email>                  # Register (interactive interest picker)
│   │   ├── --interests <csv>        # e.g. "finance,technology"
│   │   └── --depth <n>             # Briefing depth (default 10)
│   ├── ls                           # List all users (table: email, interests, format, pro, created)
│   │   └── --pro                    # Filter pro users only
│   ├── show <email>                 # Full profile + engagement stats + last briefing
│   ├── edit <email>                 # Update interests, depth, format
│   │   ├── --interests <csv>
│   │   ├── --depth <n>
│   │   └── --format <email|json_feed|audio_script>
│   └── rm <email>                   # Delete user (with confirmation prompt)
│
├── source                           # Source registry management
│   ├── ls                           # Table: name, url, trust, bias, categories, active
│   │   ├── --bias <label>           # Filter by bias label
│   │   ├── --min-trust <float>      # Filter by minimum trust score
│   │   └── --inactive               # Include deactivated sources
│   ├── add <url>                    # Add source (auto-detect RSS, prompt for trust/bias)
│   │   ├── --name <name>
│   │   ├── --trust <0.0-1.0>
│   │   ├── --bias <label>
│   │   └── --rss <rss_url>
│   ├── seed                         # Run the 30-source seed (idempotent)
│   ├── trust <url> <score>          # Update trust score
│   ├── bias <url> <label>           # Update bias label
│   └── toggle <url>                 # Activate/deactivate
│
├── story                            # Story cluster inspection
│   ├── ls                           # Recent clusters (table: id, headline, status, articles, age)
│   │   ├── --status <raw|analyzed>  # Filter by status
│   │   ├── --category <cat>         # Filter by category
│   │   └── --limit <n>             # Row limit (default 20)
│   ├── show <id>                    # Full cluster view:
│   │                                #   headline, summary, categories, article list,
│   │                                #   perspectives panel (sentiment bars, bias labels,
│   │                                #   key claims with source attribution)
│   └── stats                        # Aggregate view:
│                                    #   stories by category (bar chart),
│                                    #   stories by status (RAW/ANALYZED counts),
│                                    #   avg perspectives per cluster,
│                                    #   source distribution (which outlets appear most)
│
├── briefing                         # Briefing management
│   ├── ls                           # Recent briefings (table: id, user, stories, sent, date)
│   │   ├── --user <email>           # Filter by user
│   │   └── --unsent                 # Show failed deliveries only
│   ├── show <id>                    # Render briefing content in terminal (rich HTML->terminal)
│   ├── preview <email>              # Generate briefing without sending (dry run)
│   │                                # Renders in terminal with full formatting
│   └── resend <id>                  # Resend a previously generated briefing
│
├── docs                             # In-terminal documentation viewer
│   ├── spec                         # Render docs/specifications.md with rich markdown
│   ├── roadmap                      # Render ROADMAP.md
│   ├── arch                         # Render CLAUDE.md (architecture & constraints)
│   ├── stack                        # Render TECH_STACK.md
│   ├── readme                       # Render README.md
│   ├── search <query>               # Full-text search across all docs, show matched sections
│   └── --pager                      # Pipe through system pager (less) for long docs
│
├── config                           # Configuration inspection
│   ├── show                         # Current settings (table, secrets masked)
│   ├── check                        # Validate config + test API connectivity
│   └── env                          # Print .env template with comments
│
├── db                               # Database operations
│   ├── init                         # Create tables (idempotent)
│   ├── stats                        # Row counts per table, DB file size, WAL size
│   └── export                       # Dump to JSON (for backup/migration)
│       └── --table <name>           # Export single table
│
├── alert                            # Manual alert testing
│   └── test                         # Send test notification to ntfy
│
└── version                          # Package version + Python version + deps
```

---

## Global Flags

Every command supports:

| Flag | Effect |
|------|--------|
| `--json` | Machine-readable JSON output (no Rich formatting) |
| `--quiet` | Suppress non-essential output |
| `--db <url>` | Override database URL (useful for inspecting a backup) |

---

## Output Examples

### Status Dashboard

`prism status --watch` renders a live-updating Rich panel:

```
╭──────────────────────── Prism Pipeline Status ─────────────────────────╮
│                                                                        │
│  Pipeline          Last Run          Next Run        Result            │
│  ─────────────     ────────────      ──────────      ──────            │
│  Discovery         14:02 (26m ago)   16:02           ✓ 12 clusters    │
│  Analysis          14:30 (58s ago)   15:00           ✓ 8 analyzed     │
│  Briefing          07:00 (7h ago)    07:00 tomorrow  ✓ 3 sent         │
│                                                                        │
│  Database                     Stories                                  │
│  ──────────                   ────────                                 │
│  Clusters: 847 total          RAW: 4        ██░░░░░░░░                │
│  Articles: 3,291              ANALYZED: 843 ████████░░                │
│  Sources:  34 (30 active)                                              │
│  Users:    12 (2 pro)         Categories                               │
│                                ──────────                              │
│  Last Errors                   finance:    ████████ 31%               │
│  ────────────                  politics:   ██████   24%               │
│  (none in 48h)                 technology: █████    19%               │
│                                world:      ███      12%               │
│                                health:     ██        8%               │
│                                science:    █         4%               │
│                                sports:     █         2%               │
╰────────────────────────────────────────────────────────────────────────╯
```

### Story Detail

`prism story show 42`:

```
╭─ Cluster #42 ─────────────────────────────────────────────────────────╮
│  Fed Holds Rates Steady, Signals Caution on Inflation                 │
│  Status: ANALYZED │ Categories: finance, politics │ Articles: 6       │
│  First seen: 2026-05-19 08:14 UTC (6h ago)                           │
╰───────────────────────────────────────────────────────────────────────╯

  Summary
  The Federal Reserve held interest rates unchanged at 5.25-5.50% for the
  sixth consecutive meeting, citing persistent inflation concerns...

╭─ Perspectives ────────────────────────────────────────────────────────╮
│                                                                       │
│  Reuters [center]                              sentiment: ──●── 0.1  │
│  Fed maintained rates while acknowledging mixed inflation data.       │
│  • Core PCE rose 2.7% in April (Source: Reuters)                     │
│  • Labor market remains "solid" per Fed statement (Source: Reuters)   │
│                                                                       │
│  ─────────────────────────────────────────────────────────────────    │
│                                                                       │
│  Fox News [right]                              sentiment: ──●── -0.4 │
│  Emphasizes inflation burden on consumers, criticizes Fed inaction.   │
│  • Grocery prices up 22% since 2020 (Source: Fox News)               │
│  • "Fed is behind the curve" — Sen. Kennedy (Source: Fox News)       │
│                                                                       │
│  ─────────────────────────────────────────────────────────────────    │
│                                                                       │
│  NYT [center_left]                             sentiment: ──●── 0.3  │
│  Frames steady rates as prudent; highlights improving trends.         │
│  • Unemployment at 3.9%, near historic lows (Source: NYT)            │
│  • Fed "well-positioned to respond" to either outcome (Source: NYT)  │
│                                                                       │
╰───────────────────────────────────────────────────────────────────────╯
```

### Config Check

`prism config check`:

```
  Checking Prism configuration...

  ✓ anthropic_api_key    valid (claude-sonnet-4-6 reachable)
  ✓ brave_api_key        valid (plan: Base, 1,847 queries remaining)
  ✗ resend_api_key       missing — email delivery disabled
  ✓ database             writable, WAL mode, 7 tables, 2.4 MB
  ✓ ntfy_topic           "prism-prod" reachable
  ⚠ briefing_from_email  "briefing@yourdomain.com" (default — update before sending)

  3/4 APIs operational. 1 warning.
```

### Docs Viewer

`prism docs spec` renders the markdown with Rich:

- Headers become styled panels
- Tables render as Rich tables
- Code blocks get syntax highlighting
- `--pager` pipes through `less -R` for scrolling
- `prism docs search "retry"` greps all docs, shows matched sections with context

---

## Implementation Structure

```
src/prism/cli/
├── __init__.py
├── app.py              # typer.Typer() root + subcommand registration
├── run.py              # prism run
├── status.py           # prism status (Rich live dashboard)
├── cycle.py            # prism cycle discover|analyze|brief
├── user.py             # prism user add|ls|show|edit|rm
├── source.py           # prism source ls|add|seed|trust|bias|toggle
├── story.py            # prism story ls|show|stats
├── briefing.py         # prism briefing ls|show|preview|resend
├── docs.py             # prism docs spec|roadmap|arch|stack|search
├── config_cmd.py       # prism config show|check|env
├── db_cmd.py           # prism db init|stats|export
└── _fmt.py             # Shared formatting helpers (tables, panels, bars)
```

### Entrypoint

```toml
[project.scripts]
prism = "prism.cli.app:main"
```

After `pip install -e .`, the user types `prism` anywhere.

---

## New Dependencies

| Package | Version | Why |
|---------|---------|-----|
| typer | >= 0.12.0 | CLI framework (click-based, type-hint driven) |
| rich | >= 13.0.0 | Terminal rendering (tables, panels, live display, markdown) |

---

## Implementation Milestones (M7)

| Task | Scope |
|------|-------|
| T7.1 | Scaffold: typer app, entrypoint, `prism version`, `prism config show/check` |
| T7.2 | Data commands: `prism user`, `prism source`, `prism story`, `prism briefing` |
| T7.3 | Operations: `prism run`, `prism cycle`, `prism status` dashboard |
| T7.4 | Docs viewer: `prism docs` with markdown rendering + search |
| T7.5 | Polish: `--json` output mode, `--quiet`, error UX, help text |

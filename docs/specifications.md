# Prism -- Specifications

> **Prism** is an AI-powered news curation platform that delivers personalized,
> multi-perspective briefings by orchestrating four cooperating AI agents. Its
> core principle: _"Humans cannot be objective -- neither can AI. We make the
> bias transparent."_

---

## 1. System Overview

Prism discovers trending news across sources, analyzes each story from multiple
editorial perspectives, personalizes selections per subscriber, and delivers
attributed briefings via email. Every factual claim traces back to its origin
outlet. Bias is surfaced, not hidden.

### 1.1 Agentic Architecture

The system comprises four autonomous agents that communicate exclusively through
database state transitions -- no message broker, no shared memory, no RPC.

```
D_AI (Discovery) --> A_AI (Analysis) --> P_AI (Personalization) --> W_AI (Writer)
     |                    |                      |                      |
   Brave API           Claude API           Scoring engine          Claude API
   RSS feeds           JSON output          Engagement DB           Resend API
     |                    |                      |                      |
     v                    v                      v                      v
  StoryCluster       Perspective[]          Ranked list[]           Briefing
  status=RAW         status=ANALYZED        per user               sent=True
```

**Key design decision:** Agents discover work by polling the database for rows
matching their input state. D_AI writes `status=RAW` clusters; A_AI picks up
`RAW` and transitions to `ANALYZED`; P_AI reads `ANALYZED` clusters and scores
them; W_AI generates and delivers the final briefing. This eliminates the need
for Redis, Celery, or any inter-process coordination layer.

### 1.2 Core Invariants

| # | Invariant | Enforcement |
|---|-----------|-------------|
| I1 | Every factual claim is attributed to a named source | Prompt instructions + output validation |
| I2 | No fabricated information | Curation + summarization only, no original reporting |
| I3 | Bias is visible, not hidden | Perspectives shown explicitly with sentiment + bias labels |
| I4 | One agent failure does not crash the pipeline | Per-job try/except with alert forwarding |
| I5 | State transitions are monotonic | `RAW -> ANALYZED -> delivered` (no backward transitions) |
| I6 | Duplicate stories are merged, not duplicated | Jaccard similarity on headlines >= 0.6 threshold |

---

## 2. Agent Specifications

### 2.1 D_AI -- Discovery Agent

**Responsibility:** Find trending stories from heterogeneous sources, deduplicate,
and cluster articles covering the same event.

**Inputs:**
- Brave Search API (news endpoint, `freshness=pd`)
- RSS feeds from active, trusted sources in the Source registry

**Outputs:**
- `StoryCluster` rows with `status=RAW`
- `Article` rows linked to clusters via `cluster_id`
- `Source` rows created on first encounter (trust=0.5, bias=UNKNOWN)

**Behavioral Requirements:**

| ID | Requirement | Rationale |
|----|-------------|-----------|
| D1 | Query 6 broad topics per cycle | Ensures category diversity |
| D2 | Jaccard word-set similarity >= 0.6 merges articles into one cluster | Prevents duplicate stories in briefings |
| D3 | Cross-cycle merge: check existing clusters from last 24h before creating new ones | Ongoing stories accumulate perspectives over time |
| D4 | New sources start at trust_score=0.5, bias_label=UNKNOWN | Conservative default; manual curation upgrades |
| D5 | RSS parsing failures are logged and skipped, not fatal | One broken feed must not block discovery |
| D6 | Domain extraction strips `www.` prefix for Source dedup | `www.reuters.com` and `reuters.com` are the same outlet |
| D7 | Maximum 50 stories per cycle (`max_stories_per_cycle`) | Prevents runaway storage on high-volume news days |

**API Contract:**

```python
class DiscoveryAgent:
    def search_brave(query: str, count: int = 20) -> list[dict]
    def fetch_rss_sources(engine: Engine | None = None) -> list[dict]
    def deduplicate_articles(articles: list[dict], threshold: float = 0.6) -> list[list[dict]]
    def store_cluster(articles: list[dict], engine: Engine | None = None) -> StoryCluster | None
    def run_discovery(queries: list[str] | None = None, engine: Engine | None = None) -> None
```

### 2.2 A_AI -- Analysis Agent

**Responsibility:** Analyze story clusters using Claude to extract structured
perspectives, detect sentiment and bias, and categorize by topic.

**Inputs:**
- `StoryCluster` rows where `status=RAW`
- Associated `Article` rows (top 15 by source trust)

**Outputs:**
- Updated `StoryCluster` with headline, summary, categories, `status=ANALYZED`
- `Perspective` rows per cluster (one per source outlet)

**Behavioral Requirements:**

| ID | Requirement | Rationale |
|----|-------------|-----------|
| A1 | Truncate article snippets to fit token budget (8000 tokens, ~4 chars/token) | Prevents Claude API overrun and controls cost |
| A2 | Keep top 15 articles per cluster, sorted by source trust | Focus on highest-quality sources |
| A3 | Parse Claude response as JSON; log and skip on parse failure | No crash on malformed LLM output |
| A4 | Clamp sentiment to [-1.0, 1.0] | Defensive against LLM producing out-of-range values |
| A5 | Map unrecognized bias labels to `UNKNOWN` | Graceful handling of unexpected Claude output |
| A6 | Validate source_id exists in Source table; fallback to first article's source | No orphaned foreign keys |
| A7 | 1-second delay between Claude calls | Respect rate limits |
| A8 | Categories restricted to: finance, politics, technology, sports, culture, science, health, world | Deterministic categorization for downstream matching |

**Prompt Contract (v2):**

The analysis prompt instructs Claude to return valid JSON with:
```json
{
    "headline": "string -- concise neutral headline",
    "summary": "string -- 2-3 sentence neutral summary",
    "categories": ["string -- from fixed set"],
    "perspectives": [
        {
            "source_name": "string",
            "source_id": "int",
            "summary": "string -- how this source frames the story",
            "sentiment": "float -- [-1.0, 1.0]",
            "bias_label": "left|center_left|center|center_right|right|unknown",
            "key_claims": ["string -- each ending with (Source: outlet)"]
        }
    ]
}
```

Prompts are versioned (`ANALYSIS_PROMPT_VERSION = "2"`) and stored as module-level
constants to enable A/B testing and rollback.

**API Contract:**

```python
class AnalysisAgent:
    def analyze_cluster(cluster_id: int, engine: Engine | None = None) -> None
    def process_pending(engine: Engine | None = None) -> None
```

### 2.3 P_AI -- Personalization Agent

**Responsibility:** Score and rank stories per user based on interests, recency,
and source diversity. Filter previously seen stories.

**Inputs:**
- `StoryCluster` rows where `status=ANALYZED` and `first_seen >= 48h ago`
- `User` profile (interests, briefing_depth)
- `Engagement` history (seen stories)

**Outputs:**
- Ordered list of `StoryCluster` objects per user (top N by score)

**Scoring Formula:**

```
score = (5.0 * interest_overlap_count)
      + recency_bonus
      + min(article_count * 0.5, 3.0)

where recency_bonus:
    age < 6h  -> 3.0
    age < 24h -> 1.5
    age >= 24h -> 0.0
```

**Behavioral Requirements:**

| ID | Requirement | Rationale |
|----|-------------|-----------|
| P1 | Score is deterministic given same inputs | Reproducible for debugging |
| P2 | Exclude stories with existing Engagement records for this user | No repeat content |
| P3 | 48-hour sliding window on cluster age | Stale news has no value |
| P4 | Respect `user.briefing_depth` as max story count | User controls briefing length |
| P5 | Return stories sorted descending by score | Most relevant first |

**API Contract:**

```python
class PersonalizationAgent:
    def score_story(cluster: StoryCluster, user: User) -> float
    def select_stories(user: User, engine: Engine | None = None) -> list[StoryCluster]
    def record_engagement(user_id: int, cluster_id: int, action: str,
                          read_time_sec: int = 0, engine: Engine | None = None) -> None
    def get_all_users(engine: Engine | None = None) -> list[User]
```

### 2.4 W_AI -- Writer Agent

**Responsibility:** Generate personalized briefings from selected stories,
format for the user's preferred delivery channel, and deliver via email.

**Inputs:**
- `User` profile (interests, preferred_format)
- Selected `StoryCluster` list from P_AI
- `Perspective` rows per cluster

**Outputs:**
- `Briefing` row with content and delivery status
- Email sent via Resend (if `preferred_format == EMAIL`)

**Behavioral Requirements:**

| ID | Requirement | Rationale |
|----|-------------|-----------|
| W1 | Every factual claim ends with `(Source: <outlet>)` | Core attribution invariant |
| W2 | Lead with most important story | Reader engagement |
| W3 | Note where sources diverge on facts | Bias transparency |
| W4 | EMAIL format: clean HTML with `<h2>` headers, `<p>` text | Consistent email rendering |
| W5 | AUDIO_SCRIPT format: naturally spoken prose, no HTML | Future TTS pipeline compatibility |
| W6 | Target ~800 words for standard briefing | Optimal reading time (~3 minutes) |
| W7 | Empty story list short-circuits (no Claude call, no DB row) | No wasted API calls |
| W8 | Store Briefing row before send attempt | Audit trail even on delivery failure |
| W9 | Update `sent=True`, `sent_at` only on confirmed delivery | Accurate delivery tracking |

**Prompt Contract (v2):**

The briefing prompt is parameterized with `{interests}`, `{format}`, `{stories_json}`,
and `{story_count}`. It instructs Claude to produce attributed, format-aware content
with an "Also worth watching" section for lower-priority items.

**API Contract:**

```python
class WriterAgent:
    def build_story_data(clusters: list[StoryCluster], engine: Engine | None = None) -> list[dict]
    def generate_briefing(user: User, clusters: list[StoryCluster],
                          engine: Engine | None = None) -> str
    def send_email(user: User, content_html: str) -> bool
    def create_and_send(user: User, clusters: list[StoryCluster],
                        engine: Engine | None = None) -> Briefing | None
```

---

## 3. Data Model

### 3.1 Entity Relationships

```
Source (1) ---< Article (N) >--- StoryCluster (1)
                                       |
                                       +---< Perspective (N)
                                       |
User (1) ---< Engagement (N) >--- StoryCluster
  |
  +---< Briefing (N)
```

### 3.2 Table Specifications

**Source** -- News outlet registry with trust and bias metadata.

| Column | Type | Constraints | Default |
|--------|------|-------------|---------|
| id | int | PK, auto | -- |
| name | str | indexed | -- |
| url | str | unique | -- |
| rss_url | str | -- | "" |
| trust_score | float | 0.0-1.0 | 0.5 |
| bias_label | BiasLabel | enum | UNKNOWN |
| categories | str | comma-separated | "" |
| active | bool | -- | True |
| created_at | datetime | -- | UTC now |

**StoryCluster** -- Groups of articles covering the same event.

| Column | Type | Constraints | Default |
|--------|------|-------------|---------|
| id | int | PK, auto | -- |
| headline | str | -- | "" |
| summary | str | -- | "" |
| categories | str | comma-separated | "" |
| status | StoryStatus | enum | RAW |
| article_count | int | -- | 0 |
| first_seen | datetime | -- | UTC now |
| last_updated | datetime | -- | UTC now |

**Article** -- Individual article from a single source.

| Column | Type | Constraints | Default |
|--------|------|-------------|---------|
| id | int | PK, auto | -- |
| cluster_id | int | FK -> StoryCluster | -- |
| source_id | int | FK -> Source | -- |
| title | str | -- | -- |
| url | str | unique | -- |
| snippet | str | -- | -- |
| published_at | datetime | nullable | -- |
| fetched_at | datetime | -- | UTC now |

**Perspective** -- One outlet's framing of a story (produced by A_AI).

| Column | Type | Constraints | Default |
|--------|------|-------------|---------|
| id | int | PK, auto | -- |
| cluster_id | int | FK -> StoryCluster | -- |
| source_id | int | FK -> Source | -- |
| summary | str | -- | -- |
| sentiment | float | -1.0 to 1.0 | 0.0 |
| bias_label | BiasLabel | enum | UNKNOWN |
| key_claims | str | JSON array | "[]" |

**User** -- Subscriber profile and preferences.

| Column | Type | Constraints | Default |
|--------|------|-------------|---------|
| id | int | PK, auto | -- |
| email | str | unique, indexed | -- |
| name | str | -- | "" |
| interests | str | comma-separated | "" |
| preferred_format | BriefingFormat | enum | EMAIL |
| briefing_depth | int | -- | 10 |
| is_pro | bool | -- | False |
| created_at | datetime | -- | UTC now |

**Engagement** -- User interaction tracking for the feedback loop.

| Column | Type | Constraints | Default |
|--------|------|-------------|---------|
| id | int | PK, auto | -- |
| user_id | int | FK -> User | -- |
| cluster_id | int | FK -> StoryCluster | -- |
| action | str | open/read/save/skip | -- |
| read_time_sec | int | -- | 0 |
| created_at | datetime | -- | UTC now |

**Briefing** -- Generated and delivered newsletters.

| Column | Type | Constraints | Default |
|--------|------|-------------|---------|
| id | int | PK, auto | -- |
| user_id | int | FK -> User | -- |
| content_html | str | -- | "" |
| content_text | str | -- | "" |
| story_count | int | -- | 0 |
| sent | bool | -- | False |
| sent_at | datetime | nullable | None |
| created_at | datetime | -- | UTC now |

### 3.3 State Machine

```
StoryCluster.status:

    RAW ----[A_AI.analyze_cluster()]----> ANALYZED ----[delivered via W_AI]----> (terminal)
     ^                                       |
     |                                       v
  D_AI creates                          P_AI reads for scoring
  or merges into                        W_AI reads for briefing content
```

Transitions are **monotonic** -- a cluster never moves backward from `ANALYZED`
to `RAW`. This guarantees idempotent reprocessing: if A_AI crashes mid-batch,
only `RAW` clusters are retried on the next cycle.

---

## 4. Reliability Requirements

### 4.1 Retry with Exponential Backoff

All external API calls are wrapped with `@retry_on_transient`:

| API | Max Retries | Base Delay | Backoff Sequence |
|-----|-------------|------------|------------------|
| Brave Search | 3 | 2.0s | 2s, 4s, 8s |
| Claude (A_AI) | 3 | 2.0s | 2s, 4s, 8s |
| Claude (W_AI) | 3 | 2.0s | 2s, 4s, 8s |
| Resend email | 3 | 2.0s | 2s, 4s, 8s |

**Transient errors retried:**
- `httpx.TimeoutException`, `httpx.ConnectError`
- `ConnectionError`, `TimeoutError`
- `anthropic.RateLimitError`, `anthropic.APITimeoutError`, `anthropic.InternalServerError`
- HTTP 429 (rate limit) and 5xx (server error) status codes

**Non-transient errors raised immediately:**
- HTTP 400/401/403 (client errors)
- JSON parse failures
- Validation errors

### 4.2 Failure Isolation

Each scheduled cycle wraps its agent call in a try/except block:

```python
def discovery_cycle(engine=None):
    try:
        DiscoveryAgent().run_discovery(engine=engine or get_engine())
    except Exception as exc:
        logger.exception("Discovery cycle failed")
        send_alert(f"Discovery cycle failed: {exc}", level=AlertLevel.ERROR)
```

**Guarantees:**
- A Brave API outage does not block analysis of existing clusters
- A Claude API error on one cluster does not abort the batch
- An email delivery failure does not crash the briefing cycle
- The scheduler continues running after any individual cycle failure

### 4.3 Monitoring and Alerting

Push notifications via ntfy.sh:

| Alert Trigger | Level | Action |
|---------------|-------|--------|
| Agent cycle exception | ERROR | Immediate push notification |
| Email delivery failure | ERROR | Push + log |
| Configuration: `ntfy_topic` empty | -- | Alerting silently disabled |

Alert payload:
- **Title:** `Prism {LEVEL}: pipeline alert`
- **Priority:** INFO=3, WARNING=4, ERROR=5
- **Tags:** `prism,{level}`
- **Body:** Error message with context

**Design constraint:** Alert delivery failure must never crash the pipeline.
`send_alert()` catches all exceptions internally.

### 4.4 Database Reliability

- **WAL mode** (`PRAGMA journal_mode=WAL`): Concurrent reads from overlapping
  scheduled jobs without `database is locked` errors
- **Foreign keys enforced** (`PRAGMA foreign_keys=ON`): No orphaned articles,
  perspectives, or engagements
- **Idempotent schema creation**: `init_db()` is safe to call multiple times
- **No ORM-level cascades for deletion**: Data is append-only in normal operation

### 4.5 Graceful Shutdown

Signal handlers (SIGINT, SIGTERM) trigger `scheduler.shutdown(wait=False)`
followed by `sys.exit(0)`. In-flight database transactions are committed or
rolled back by SQLAlchemy's session management.

---

## 5. Scheduling and Orchestration

### 5.1 Job Schedule

| Job | Type | Schedule | Function |
|-----|------|----------|----------|
| Discovery | Interval | Every 2 hours (configurable) | `discovery_cycle()` |
| Analysis | Interval | Every 30 minutes | `analysis_cycle()` |
| Briefing | Cron | Daily at 07:00 (configurable) | `briefing_cycle()` |

**Orchestrator:** APScheduler `BlockingScheduler` -- single-process, no worker
pool. Each job runs sequentially within its schedule. Jobs from different
schedules may overlap (e.g., analysis runs while discovery is in progress),
which is safe due to SQLite WAL mode.

### 5.2 Briefing Cycle Flow

```python
for user in p_ai.get_all_users(engine):
    stories = p_ai.select_stories(user, engine)
    w_ai.create_and_send(user, stories, engine)
```

Users are processed sequentially. Each user gets an independent story selection
and briefing generation. One user's delivery failure does not affect others.

---

## 6. External API Integrations

### 6.1 Brave Search API

- **Endpoint:** `https://api.search.brave.com/res/v1/news/search`
- **Authentication:** `X-Subscription-Token` header
- **Parameters:** `q` (query), `count` (max 20), `freshness=pd` (past day)
- **Rate limit:** Handled via retry decorator on 429
- **Cost:** ~$5/month for 2,000 queries (Base plan)

### 6.2 Anthropic Claude API

- **Model:** `claude-sonnet-4-6`
- **Max tokens:** 4,096 per response
- **Usage:**
  - A_AI: Structured JSON analysis of article clusters
  - W_AI: Formatted briefing generation (HTML or prose)
- **Input budget:** 8,000 tokens (~32,000 chars) per cluster
- **Cost:** ~$30-80/month depending on story volume

### 6.3 Resend Email API

- **Usage:** Transactional email delivery for briefings
- **From address:** Configurable via `briefing_from_email`
- **Free tier:** 100 emails/day
- **Retry:** `extra_exceptions=(Exception,)` since Resend SDK does not use
  httpx-style error hierarchy

### 6.4 ntfy.sh

- **Usage:** Push notifications for pipeline monitoring
- **Endpoint:** `https://ntfy.sh/{topic}`
- **Authentication:** None (topic-based)
- **Optional:** Empty `ntfy_topic` disables alerting silently

---

## 7. Quality Requirements

### 7.1 Attribution

Every factual claim in both analysis output and briefing content must end with
`(Source: <outlet name>)`. This is enforced at two levels:

1. **Prompt-level:** Both `ANALYSIS_PROMPT` and `BRIEFING_PROMPT` contain
   explicit instructions requiring attribution
2. **Test-level:** `test_prompt_quality.py` validates that prompts contain
   `(Source:` references and that output schemas enforce attributed claims

### 7.2 Prompt Versioning

Prompts are stored as module-level string constants with version identifiers:

```python
ANALYSIS_PROMPT_VERSION = "2"
BRIEFING_PROMPT_VERSION = "2"
```

Version changes are committed alongside prompt text changes, enabling:
- Rollback to prior prompt versions
- A/B testing between versions
- Audit trail of prompt evolution

### 7.3 Bias Transparency

- Each `Perspective` carries `sentiment` (-1.0 to 1.0) and `bias_label`
  (left / center_left / center / center_right / right / unknown)
- Briefings explicitly note where sources diverge on facts
- Source registry carries pre-assigned `trust_score` and `bias_label` for
  30 curated outlets spanning the political spectrum

### 7.4 Category Taxonomy

Fixed set of 8 categories: `finance`, `politics`, `technology`, `sports`,
`culture`, `science`, `health`, `world`. Used consistently across:
- A_AI categorization output
- User interest selection (onboarding validation)
- P_AI interest matching (scoring formula)

---

## 8. User Management

### 8.1 Registration

Users register with email and optional interests:

```python
register_user(
    email: str,                    # required, validated, case-insensitive
    interests: str = "",           # comma-separated from fixed category set
    briefing_depth: int = 10,      # stories per briefing
    engine: Engine | None = None,
) -> User
```

**Validation rules:**
- Email must match `^[^@\s]+@[^@\s]+\.[^@\s]+$`
- Email is normalized: `strip().lower()`
- Duplicate emails are rejected (case-insensitive)
- Interests must be from the valid category set
- Invalid interests raise `RegistrationError`

**Defaults:**
- `preferred_format = BriefingFormat.EMAIL`
- `briefing_depth = 10`
- `is_pro = False`
- `interests = ""`

### 8.2 Tiers

| Feature | Free | Pro ($7/mo) |
|---------|------|-------------|
| Categories | 1 topic | All topics |
| Format | Email only | Email + JSON + Audio |
| Briefing depth | 10 stories | Up to 25 stories |
| Delivery | Daily | Daily |

---

## 9. Testability

### 9.1 Engine Injection Pattern

Every agent method that touches the database accepts an optional
`engine: Engine | None = None` parameter. When `None`, it falls back to the
global singleton via `get_engine()`. Tests inject a fresh SQLite engine
pointing to `tmp_path`:

```python
@pytest.fixture()
def db_engine(tmp_path):
    engine = init_db(f"sqlite:///{tmp_path / 'test.db'}")
    yield engine
    engine.dispose()
```

This pattern enables:
- Fully isolated test databases (no shared state between tests)
- No mocking of database internals
- Real SQL execution in tests (not just ORM-level mocking)

### 9.2 Session Handling in Tests

Tests that create objects in one session and pass them to agent methods use
`expire_on_commit=False` to prevent `DetachedInstanceError`:

```python
with Session(db_engine, expire_on_commit=False) as session:
    user = User(email="test@example.com")
    session.add(user)
    session.commit()
# user attributes are still accessible after session close
```

### 9.3 Datetime Handling

SQLite strips timezone information from datetime columns. Code must handle
the naive/aware mismatch:

- **For Python comparison:** Convert naive DB datetimes to aware:
  `if dt.tzinfo is None: dt = dt.replace(tzinfo=UTC)`
- **For SQL queries:** Strip timezone from Python datetimes:
  `cutoff = datetime.now(UTC).replace(tzinfo=None)`

### 9.4 Test Coverage

| Module | Test File | Test Count |
|--------|-----------|------------|
| Database & models | test_db.py | ~14 |
| Discovery (D_AI) | test_discovery.py | ~15 |
| Analysis (A_AI) | test_analysis.py | ~11 |
| Personalization (P_AI) | test_personalization.py | ~12 |
| Briefing (W_AI) | test_briefing.py | ~21 |
| Scheduler | test_scheduler.py | ~6 |
| End-to-end | test_e2e.py | ~3 |
| Retry | test_retry.py | ~11 |
| Alerts | test_alerts.py | ~8 |
| Prompt quality | test_prompt_quality.py | ~13 |
| Onboarding | test_onboarding.py | ~10 |
| Source seeding | test_seed.py | ~3 |
| Configuration | test_config.py | ~3 |
| **Total** | | **~146** |

---

## 10. Infrastructure

### 10.1 Deployment Target

Single VPS (Hetzner CX32, ~$15/month). All four agents run as one Python
process orchestrated by APScheduler. No containers, no Kubernetes, no
microservice decomposition.

### 10.2 Database

SQLite with WAL mode. Sufficient for the first 10,000 users. Migration path
to PostgreSQL when concurrent write contention becomes measurable.

### 10.3 Cost Model

| Component | Monthly Cost |
|-----------|-------------|
| VPS (Hetzner CX32) | $15 |
| Claude API | $30-80 |
| Brave Search API | $5 |
| Resend (email) | $0 (free tier) |
| **Total** | **~$50-100** |

### 10.4 Scaling Strategy

- **Horizontal channel scaling:** Multiple niche topic channels, not one
  megaservice
- **Database migration:** SQLite -> PostgreSQL at ~5,000+ active users
- **Email scaling:** Resend free -> paid tier ($20/month) at volume
- **Future additions:** FastAPI web interface, TTS audio briefings, engagement
  webhooks

---

## 11. Configuration Reference

All settings are loaded from `.env` via `pydantic-settings`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `anthropic_api_key` | str | _required_ | Claude API key |
| `brave_api_key` | str | "" | Brave Search API key |
| `resend_api_key` | str | "" | Resend email API key |
| `database_url` | str | `sqlite:///data/newsgen.db` | SQLAlchemy database URL |
| `briefing_from_email` | str | `briefing@yourdomain.com` | Email sender address |
| `discovery_interval_hours` | int | 2 | Hours between discovery cycles |
| `max_stories_per_cycle` | int | 50 | Max stories stored per discovery run |
| `min_source_trust_score` | float | 0.5 | Minimum source trust threshold |
| `max_perspectives_per_story` | int | 5 | Max perspectives per cluster |
| `max_input_tokens` | int | 8000 | Token budget for Claude input |
| `default_briefing_stories` | int | 10 | Default stories per briefing |
| `max_briefing_stories` | int | 25 | Maximum stories per briefing (pro) |
| `briefing_schedule_cron` | str | `0 7 * * *` | Daily briefing cron expression |
| `ntfy_topic` | str | "" | ntfy.sh topic (empty = disabled) |

---

## 12. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| anthropic | >= 0.40.0 | Claude API client |
| httpx | >= 0.27.0 | HTTP client for Brave Search |
| sqlmodel | >= 0.0.22 | SQLAlchemy + Pydantic ORM |
| pydantic | >= 2.9.0 | Data validation |
| pydantic-settings | >= 2.6.0 | Configuration from .env |
| python-dotenv | >= 1.0.1 | Environment file loading |
| apscheduler | >= 3.10.4 | Job scheduling |
| feedparser | >= 6.0.11 | RSS feed parsing |
| resend | >= 2.5.0 | Email delivery |
| jinja2 | >= 3.1.4 | Template rendering |

**Dev dependencies:** pytest, pytest-asyncio, ruff, mypy

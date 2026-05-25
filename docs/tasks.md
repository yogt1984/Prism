# Architecture Improvement Tasks

Each task is scoped for a single Opus iteration with clear deliverables and test criteria.

---

## M11 — Security Hardening

### T11.1: Hash API keys at rest

**Files:** `src/prism/models.py`, `src/prism/api/routes.py`, `src/prism/onboarding.py`

- Add `api_key_hash` field to `User` model, keep `api_key` only for the initial reveal
- Hash keys with `hashlib.sha256` on creation (no need for bcrypt — keys are high-entropy)
- Update `require_api_key()` to compare against `api_key_hash` instead of plaintext
- Clear plaintext `api_key` after first retrieval (or store only the hash)
- Update `generate_api_key()` to return `(raw_key, hashed_key)` tuple

**Tests:**
- Verify auth succeeds when header matches the original raw key
- Verify auth fails with wrong key
- Verify stored `api_key_hash` is not equal to the raw key
- Verify `create_user` response includes the raw key exactly once

---

### T11.2: Add API rate limiting

**Files:** `src/prism/api/app.py`, new `src/prism/api/rate_limit.py`

- Add in-memory sliding-window rate limiter (dict of `{ip: deque[timestamp]}`)
- Default: 60 requests/minute per IP for public endpoints, 120/min for authenticated
- Return `429 Too Many Requests` with `Retry-After` header when exceeded
- Implement as FastAPI middleware

**Tests:**
- Verify requests under limit return 200
- Verify request at limit+1 returns 429 with `Retry-After` header
- Verify different IPs have independent counters
- Verify window slides (old entries expire)

---

### T11.3: Enforce user-scoped access on authenticated endpoints

**Files:** `src/prism/api/routes.py`

- Currently any valid API key can access any user's data (`GET /users/{id}`)
- Add check: `auth_user.id == user_id` (or introduce admin role later)
- Return 403 if authenticated user tries to access another user's resources
- Apply to: `get_user`, `update_user`, `list_briefings`, `get_briefing`, `trigger_briefing`

**Tests:**
- Verify user A cannot read user B's profile
- Verify user A cannot list user B's briefings
- Verify user A can access their own resources normally
- Verify 403 response body includes clear error message

---

## M12 — Engagement-Based Personalization

### T12.1: Add engagement weight calculation to P_AI

**Files:** `src/prism/agents/p_ai.py`

- Add `_compute_engagement_weights(user_id, engine) -> dict[str, float]` method
- Query last 30 days of engagements for the user
- Calculate per-category affinity: `save` = +2.0, `read` (>30s) = +1.0, `open` = +0.5, `skip` = -1.0
- Normalize to 0.0-1.0 range per category
- Return `{"finance": 0.8, "politics": 0.3, ...}`

**Tests:**
- User with 5 saves on "finance" stories gets high finance weight
- User with all skips on "sports" gets low/zero sports weight
- Empty engagement history returns empty dict (no crash)
- Mixed actions produce expected normalized scores

---

### T12.2: Integrate engagement weights into story scoring

**Files:** `src/prism/agents/p_ai.py`

- Modify `score_story()` to accept optional `engagement_weights: dict[str, float]`
- Add engagement bonus: `sum(weights.get(cat, 0) * 3.0 for cat in story_categories)`
- Update `select_stories()` to call `_compute_engagement_weights()` once, pass to each `score_story()` call
- Log when engagement data changes story ordering vs static interests

**Tests:**
- Story in category with high engagement weight scores higher than without
- Engagement weights don't override interest match (interest still contributes +5.0)
- With no engagement data, scoring is identical to current behavior (backward compatible)
- Verify sort order changes when engagement weights favor a different category

---

## M13 — Deduplication Improvement

### T13.1: Add TF-IDF-based similarity as Jaccard fallback

**Files:** `src/prism/agents/d_ai.py`

- Add `_tfidf_similarity(a: str, b: str) -> float` using `sklearn.feature_extraction.text.TfidfVectorizer` with cosine similarity
- Only import sklearn lazily (optional dependency) — fall back to Jaccard-only if unavailable
- Update `deduplicate_articles()`: if Jaccard < threshold but > 0.4, check TF-IDF as tiebreaker (threshold 0.5)
- Add `scikit-learn` as optional dependency in `pyproject.toml` (`[project.optional-dependencies]`)

**Tests:**
- Two articles with same event but different wording cluster together (TF-IDF catches what Jaccard misses)
- Two articles with similar vocabulary but different events stay separate
- System works without sklearn installed (graceful fallback to Jaccard-only)
- Performance: deduplicate 200 articles in <2 seconds

---

### T13.2: Add named entity overlap to dedup scoring

**Files:** `src/prism/agents/d_ai.py`

- Add `_entity_overlap(a: str, b: str) -> float` using capitalized word extraction (no spaCy dependency)
- Extract capitalized multi-word sequences (e.g., "Federal Reserve", "Elon Musk") via regex
- Compute Jaccard on entity sets
- Integrate as third signal in `deduplicate_articles()`: `combined = 0.5*jaccard + 0.3*tfidf + 0.2*entity`
- Fall back to Jaccard-only if neither TF-IDF nor entity extraction improves confidence

**Tests:**
- Articles mentioning same person/company cluster even with different headlines
- Articles mentioning different entities in same domain stay separate
- Empty/short titles don't crash entity extraction
- Combined score is bounded [0.0, 1.0]

---

## M14 — Database Migration Path

### T14.1: Add Alembic migration infrastructure

**Files:** new `alembic.ini`, new `alembic/env.py`, new `alembic/versions/001_initial.py`

- Install alembic as dependency
- Configure alembic to use `prism.config.settings.database_url`
- Generate initial migration from current SQLModel metadata (autogenerate)
- Update `init_db()` to check if alembic is managing the schema (look for `alembic_version` table)
- Add `prism db upgrade` CLI command to run migrations

**Tests:**
- Fresh database: `alembic upgrade head` creates all tables matching current schema
- Existing database: migration detects `alembic_version` table and skips `create_all`
- `alembic downgrade -1` from initial migration drops all tables cleanly
- CLI `prism db upgrade` runs without error on empty database

---

### T14.2: Add created_at index migration

**Files:** new `alembic/versions/002_add_datetime_indexes.py`

- Add indexes on: `StoryCluster.first_seen`, `Article.fetched_at`, `Briefing.created_at`, `Engagement.created_at`
- These are the columns used in time-range queries (48h cutoff, 24h cluster merge window)
- Write as explicit alembic migration (not autogenerate) for clarity

**Tests:**
- Migration applies cleanly on existing populated database
- Downgrade removes the indexes
- Query with `WHERE first_seen >= cutoff` uses index (check via `EXPLAIN QUERY PLAN`)
- No data loss after migration round-trip (upgrade + downgrade + upgrade)

---

## M15 — Observability

### T15.1: Add structured metrics collection

**Files:** new `src/prism/metrics.py`, `src/prism/main.py`

- Create simple counter/gauge/histogram classes stored in a module-level dict
- Track: `discovery_articles_total`, `discovery_clusters_stored`, `analysis_duration_seconds`, `briefing_sent_total`, `api_requests_total`
- Agents increment counters at cycle boundaries
- Add `GET /metrics` endpoint returning JSON snapshot of all metrics

**Tests:**
- Counter increments correctly across multiple calls
- Histogram records values and computes min/max/avg/count
- `GET /metrics` returns all registered metrics as JSON
- Metrics survive across agent cycles (module-level state persists)

---

### T15.2: Add per-cycle timing and status logging

**Files:** `src/prism/main.py`, `src/prism/agents/d_ai.py`, `src/prism/agents/a_ai.py`, `src/prism/agents/w_ai.py`

- Add `@timed_cycle` decorator that logs cycle name, duration, success/failure, and updates metrics
- Apply to `run_discovery()`, `process_pending()`, `create_and_send()`
- On failure: log error + increment `cycle_failures_total` counter
- On success: log duration + increment `cycle_successes_total`

**Tests:**
- Successful cycle logs duration and increments success counter
- Failed cycle (raised exception) logs error and increments failure counter
- Decorator preserves function signature and return value
- Timer accuracy within 50ms tolerance

---

## M16 — Delivery Formats

### T16.1: Implement JSON feed briefing format

**Files:** `src/prism/agents/w_ai.py`

- Add `_format_json_feed(user, stories, briefing_content) -> str` method
- Output JSON with: `version`, `title`, `items[]` (each with `id`, `headline`, `summary`, `perspectives[]`, `categories`, `sources[]`)
- Store in `Briefing.content_text` (keep `content_html` empty for JSON format)
- Update `create_and_send()` to route `BriefingFormat.JSON_FEED` to this formatter instead of email
- Skip email delivery for JSON format (API-only retrieval)

**Tests:**
- JSON feed output is valid JSON and matches expected schema
- Each item includes all perspectives with source attribution
- Pro user with `preferred_format=json_feed` gets JSON briefing stored correctly
- JSON briefing is not sent via email (no Resend call)

---

### T16.2: Implement audio script briefing format

**Files:** `src/prism/agents/w_ai.py`

- Add `_format_audio_script(user, stories, briefing_content) -> str` method
- Modify Claude prompt to generate a spoken-word script: conversational tone, phonetic guidance for names, transition phrases between stories
- Store in `Briefing.content_text` with `content_html` empty
- Skip email delivery for audio format (API-only retrieval)
- Target ~3 minutes reading time (~450 words)

**Tests:**
- Audio script does not contain HTML tags
- Script includes transition phrases between stories
- Script includes source attribution in spoken form ("according to Reuters")
- Pro user with `preferred_format=audio_script` gets script stored correctly

---

## M17 — Prompt Quality

### T17.1: Add prompt version tracking to briefings

**Files:** `src/prism/models.py`, `src/prism/agents/a_ai.py`, `src/prism/agents/w_ai.py`

- Add `prompt_version` field to `StoryCluster` (analysis prompt version) and `Briefing` (briefing prompt version)
- Set `prompt_version` when A_AI analyzes or W_AI generates
- Store prompt version constants as module-level `PROMPT_VERSION = "2"` (already exists in a_ai, add to w_ai)
- Add `prompt_version` to `StoryOut` and `BriefingOut` API response schemas

**Tests:**
- Newly analyzed cluster has `prompt_version` set to current A_AI version
- Newly generated briefing has `prompt_version` set to current W_AI version
- API responses include `prompt_version` field
- Alembic migration adds the column with default empty string (backward compatible)

---

### T17.2: Add output quality validation for A_AI

**Files:** `src/prism/agents/a_ai.py`

- Add `_validate_analysis(result: dict) -> list[str]` returning list of quality issues
- Check: summary length (50-500 chars), at least 2 perspectives, all perspectives have non-empty `key_claims`, sentiment values in range, no duplicate source_ids
- Log warnings for quality issues but don't block storage
- Add `quality_score` field to `StoryCluster` (0.0-1.0 based on checks passed / total checks)

**Tests:**
- Perfect analysis returns empty issue list and quality_score 1.0
- Missing perspectives returns issue and lower quality_score
- Out-of-range sentiment is flagged
- Duplicate source_ids in perspectives are flagged
- Short/empty summary is flagged

---

## M18 — Resilience

### T18.1: Add circuit breaker for external API calls

**Files:** new `src/prism/circuit_breaker.py`, `src/prism/agents/d_ai.py`, `src/prism/agents/a_ai.py`

- Implement simple circuit breaker: states `CLOSED` (normal), `OPEN` (failing, reject calls), `HALF_OPEN` (test one call)
- Config: `failure_threshold=5`, `recovery_timeout=300` seconds
- When open, raise `CircuitOpenError` immediately instead of hitting the API
- Apply to Brave API calls and Claude API calls independently (separate breaker per service)

**Tests:**
- After 5 consecutive failures, breaker opens and raises `CircuitOpenError`
- After recovery timeout, breaker moves to half-open and allows one call
- Successful call in half-open resets to closed
- Failed call in half-open reopens the breaker
- Independent breakers don't affect each other

---

### T18.2: Add graceful degradation for discovery when Brave is down

**Files:** `src/prism/agents/d_ai.py`

- When `CircuitOpenError` is raised for Brave, fall back to RSS-only discovery
- Log warning: "Brave API circuit open, running RSS-only discovery cycle"
- Track `discovery_brave_skip_total` metric
- When circuit recovers, resume normal Brave+RSS discovery

**Tests:**
- With Brave circuit open, discovery still runs and stores clusters from RSS
- Warning is logged when falling back to RSS-only
- Metric is incremented on each Brave-skipped cycle
- When Brave circuit closes, next cycle includes Brave results again

---

## Dependency Graph

```
M11 (Security) ── no dependencies, start here
M12 (Engagement) ── no dependencies
M13 (Dedup) ── T13.2 depends on T13.1
M14 (Migrations) ── T14.2 depends on T14.1; T17.1 depends on T14.1
M15 (Observability) ── T15.2 depends on T15.1; T18.1 reads metrics from T15.1
M16 (Delivery) ── no dependencies
M17 (Prompts) ── T17.1 depends on T14.1 (needs migration for new columns)
M18 (Resilience) ── T18.1 depends on T15.1 (metrics); T18.2 depends on T18.1
```

**Recommended execution order:** M11 > M14 > M15 > M12 > M13 > M17 > M18 > M16

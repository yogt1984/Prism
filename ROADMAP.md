# Prism — Implementation Roadmap

## Milestones

| # | Milestone | Definition of Done | Target |
|---|-----------|-------------------|--------|
| M0 | **Foundation** | DB (WAL mode), config, CI all working. `pytest` green on empty pipeline. | Week 1 |
| M1 | **Discovery Loop** | D_AI fetches real news from Brave API, deduplicates (within + across cycles), stores clusters in DB. | Week 2 |
| M2 | **Analysis Pipeline** | A_AI produces structured multi-perspective summaries with token budget control. | Week 3 |
| M3 | **Personalization + Delivery** | P_AI scores stories, W_AI generates and sends a real email briefing to a test inbox. | Week 4 |
| M4 | **End-to-End Loop** | Full pipeline runs on schedule via DB state machine: discover → analyze → personalize → deliver. | Week 5 |
| M5 | **Hardening** | Error recovery, monitoring, prompt quality iteration. Source trust is manually curated. | Week 6-7 |
| M6 | **Beta Launch** | 10-20 real users receiving daily briefings. Manual feedback collection. | Week 8 |

### Design Decisions

- **No Redis.** Agents communicate via DB status fields (`StoryStatus.RAW → ANALYZED`). All agents run on one box via APScheduler. DB polling every 30m is sufficient at this scale.
- **No datasketch for MVP.** Story deduplication uses simple word-set Jaccard similarity. Add MinHash if article volume exceeds 1k/cycle.
- **No automated trust tuning.** Source trust/bias scores are manually curated. Seed 20-30 known outlets at launch.
- **No engagement webhooks for beta.** Tracking pixels require a web server. Collect beta feedback via direct user surveys instead.
- **SQLite in WAL mode.** Allows concurrent reads from overlapping scheduled jobs without `database is locked` errors.

---

## M0 — Foundation

### T0.1: Database initialization with WAL mode

**Task:** `init_db()` creates all tables with WAL journal mode enabled.

**Tests (write before implementing):**
```
test_init_db_creates_all_tables     — call init_db(), assert all tables exist via inspector
test_init_db_idempotent             — call init_db() twice, no error
test_wal_mode_enabled               — PRAGMA journal_mode returns "wal"
test_session_crud_source            — insert, read, update, delete a Source row
test_session_crud_story_cluster     — same for StoryCluster + Article relationship
test_session_crud_user              — same for User
test_foreign_key_integrity          — Article with invalid cluster_id raises IntegrityError
test_concurrent_read_write          — reader thread doesn't block writer thread
```

**Acceptance criteria:**
- [ ] `init_db()` is idempotent (safe to call multiple times)
- [ ] SQLite WAL mode is enabled (`PRAGMA journal_mode=WAL`)
- [ ] Foreign keys are enforced (`PRAGMA foreign_keys=ON`)
- [ ] All SQLModel tables from `models.py` are created
- [ ] `get_session()` returns a working session that can CRUD all models
- [ ] Concurrent read+write from two threads does not raise `database is locked`

### T0.2: Configuration validation

**Task:** Settings load from `.env`, fail fast on missing required keys.

**Tests:**
```
test_settings_loads_from_env       — mock .env, verify all fields populated
test_settings_missing_api_key      — no ANTHROPIC_API_KEY raises ValidationError
test_settings_defaults             — verify default values for optional fields
```

**Acceptance criteria:**
- [ ] `settings.anthropic_api_key` loads from env
- [ ] Missing required key raises a clear error at startup, not at first use
- [ ] All default values match TECH_STACK.md specifications

### T0.3: CI pipeline

**Task:** GitHub Actions runs ruff + mypy + pytest on push.

**Tests:**
```
(manual) push to repo, verify Actions run green
```

**Acceptance criteria:**
- [ ] `.github/workflows/ci.yml` exists
- [ ] Runs: `ruff check`, `mypy src/`, `pytest tests/`
- [ ] Fails the build on any lint/type/test error

---

## M1 — Discovery Loop (D_AI)

### T1.1: Brave Search API integration

**Task:** `search_brave()` fetches real news results and parses them.

**Tests:**
```
test_search_brave_returns_results      — mock httpx response, verify parsed structure
test_search_brave_handles_empty        — empty results return []
test_search_brave_handles_rate_limit   — 429 response raises descriptive error
test_search_brave_handles_timeout      — timeout raises descriptive error
```

**Acceptance criteria:**
- [ ] Returns list of dicts with at minimum: `title`, `url`, `description`, `source`
- [ ] Verify Brave News API freshness parameter behavior against actual docs (do not assume `freshness=pd` works on `/news/search`)
- [ ] Rate limit (429) and timeout errors are caught and logged, not swallowed silently
- [ ] Single integration test with real API key passes (marked `@pytest.mark.integration`)

### T1.2: RSS feed polling

**Task:** `fetch_rss_sources()` reads feeds from registered sources.

**Tests:**
```
test_parse_rss_feed              — mock feedparser with sample XML, verify article extraction
test_rss_skips_inactive_sources  — source with active=False is not polled
test_rss_handles_malformed_feed  — broken XML logs warning, returns []
test_rss_dedup_by_url            — same article URL is not inserted twice
```

**Acceptance criteria:**
- [ ] Reads RSS URLs from Source table where `active=True`
- [ ] Extracts title, url, snippet, published_at from each entry
- [ ] Malformed feeds are logged and skipped, not fatal
- [ ] Duplicate URLs (already in Article table) are skipped

### T1.3: Story deduplication (within + across cycles)

**Task:** `deduplicate_articles()` groups articles about the same event. Must also merge into existing clusters from prior cycles.

**Tests:**
```
test_identical_titles_clustered          — two articles with same title → one cluster
test_similar_titles_clustered            — "Fed raises rates" and "Federal Reserve hikes interest rates" → one cluster
test_unrelated_articles_separate         — "Fed raises rates" and "Olympics 2026" → two clusters
test_empty_input_returns_empty           — [] → []
test_cross_cycle_merge                   — article matching existing cluster from 2h ago merges into it
test_cross_cycle_no_merge_after_48h      — article matching a 3-day-old cluster creates a new one
```

**Acceptance criteria:**
- [ ] Uses word-set Jaccard similarity on article titles (lowercase, stopwords removed)
- [ ] Articles with >0.6 Jaccard score are grouped into the same cluster
- [ ] Before creating a new cluster, checks existing clusters from the last 24h for matches
- [ ] If a match is found, new articles are merged into the existing cluster (cluster.article_count updated)
- [ ] Handles 200+ articles per cycle without performance issues

### T1.4: Source registry management

**Task:** `_get_or_create_source()` maintains the source table.

**Tests:**
```
test_new_source_created            — unknown domain creates Source with trust=0.5
test_existing_source_reused        — same domain returns existing Source, no duplicate
test_domain_extraction_www         — "https://www.reuters.com/article/..." → "reuters.com"
test_domain_extraction_subdomain   — "https://news.bbc.co.uk/..." → "bbc.co.uk"
```

**Acceptance criteria:**
- [ ] New sources start at `trust_score=0.5`, `bias_label=unknown`
- [ ] Domain extraction strips `www.` prefix
- [ ] No duplicate Source rows for the same domain

### T1.5: Seed trusted sources

**Task:** Populate Source table with 20-30 known outlets and hand-assigned trust/bias labels.

**Tests:**
```
test_seed_sources_creates_rows     — after seeding, Source table has ≥20 rows
test_seed_sources_idempotent       — running seed twice doesn't duplicate
test_seeded_sources_have_rss       — all seeded sources have rss_url populated
```

**Acceptance criteria:**
- [ ] Includes major wire services: Reuters, AP, AFP
- [ ] Includes left/center/right outlets for political diversity
- [ ] Each source has: name, url, rss_url, trust_score, bias_label, categories
- [ ] Seed script is idempotent

### T1.6: Full discovery cycle

**Task:** `run_discovery()` executes the complete D_AI loop.

**Tests:**
```
test_run_discovery_stores_clusters     — mock Brave + RSS, verify StoryCluster rows in DB
test_run_discovery_logs_stats          — verify log output includes article/cluster counts
test_run_discovery_handles_api_failure — Brave API down → RSS still runs, partial results stored
test_run_discovery_merges_cross_cycle  — second run merges into existing clusters where appropriate
```

**Acceptance criteria:**
- [ ] Queries all configured topics via Brave API
- [ ] Fetches all active RSS sources
- [ ] Deduplicates combined results (within-cycle and cross-cycle)
- [ ] Stores clusters + articles in DB with `status=RAW`
- [ ] Partial failures (one API down) don't block the rest

---

## M2 — Analysis Pipeline (A_AI)

### T2.1: Token budget and input truncation

**Task:** Before sending articles to Claude, truncate to fit within a token budget.

**Tests:**
```
test_truncate_respects_budget        — 20 long articles truncated to fit budget
test_truncate_preserves_all_short    — 5 short articles all included in full
test_truncate_keeps_title_and_url    — truncated articles still have title + url
test_truncate_distributes_evenly     — each article gets fair share of budget
```

**Acceptance criteria:**
- [ ] Total input to Claude stays under 8,000 tokens (configurable)
- [ ] Truncation removes snippet text first, always preserves title + url
- [ ] If cluster has >15 articles, keep the 15 from highest-trust sources
- [ ] Token count estimated at 4 chars/token (conservative)

### T2.2: Cluster analysis via Claude

**Task:** `analyze_cluster()` sends articles to Claude and parses structured output.

**Tests:**
```
test_analyze_cluster_parses_json         — mock Claude response, verify Perspective rows created
test_analyze_cluster_extracts_headline   — cluster.headline updated from Claude output
test_analyze_cluster_assigns_categories  — cluster.categories populated
test_analyze_cluster_handles_bad_json    — malformed Claude output logs error, doesn't crash
test_analyze_cluster_skips_empty         — cluster with 0 articles is skipped
```

**Acceptance criteria:**
- [ ] Input is truncated via T2.1 before sending to Claude
- [ ] Parses JSON response into: headline, summary, categories, perspectives[]
- [ ] Each perspective has: source_id, summary, sentiment, bias_label, key_claims
- [ ] Malformed JSON from Claude is logged and the cluster is skipped (not retried endlessly)
- [ ] Cluster status transitions from `RAW` → `ANALYZED`

### T2.3: Perspective storage and attribution

**Task:** Every claim in a perspective traces back to a source.

**Tests:**
```
test_perspective_links_to_source    — perspective.source_id matches a valid Source row
test_key_claims_are_valid_json      — key_claims field parses as JSON array
test_sentiment_range                — sentiment is between -1.0 and 1.0
test_bias_label_valid_enum          — bias_label is a valid BiasLabel value
test_invalid_bias_label_mapped      — unrecognized label from Claude → UNKNOWN
```

**Acceptance criteria:**
- [ ] No orphaned perspectives (every perspective.source_id exists in Source table)
- [ ] key_claims is a JSON array of strings, each containing "(Source: ...)"
- [ ] Sentiment is clamped to [-1.0, 1.0]
- [ ] Invalid bias labels from Claude are mapped to `UNKNOWN`

### T2.4: Batch processing

**Task:** `process_pending()` analyzes all RAW clusters.

**Tests:**
```
test_process_pending_finds_raw_only   — ANALYZED clusters are not re-processed
test_process_pending_handles_failure  — one cluster fails, others still process
test_process_pending_delays_calls     — 1s gap between Claude API calls
```

**Acceptance criteria:**
- [ ] Only processes clusters with `status=RAW`
- [ ] Individual cluster failure does not abort the batch
- [ ] Adds 1s delay between Claude calls to respect rate limits

---

## M3 — Personalization + Briefing Delivery (P_AI + W_AI)

### T3.1: Story scoring algorithm

**Task:** `score_story()` produces deterministic relevance scores.

**Tests (extend existing test_personalization.py):**
```
test_score_interest_match           — (exists) interest overlap boosts score
test_score_no_interest_match        — (exists) no overlap gives low score
test_score_recency_tiers            — (exists) fresher stories score higher
test_score_diversity_bonus          — more perspectives = higher score
test_score_diversity_capped         — diversity bonus caps at 3.0
test_score_empty_interests          — user with no interests still gets recency + diversity
test_score_multiple_interest_match  — story matching 3 interests scores higher than 1
```

**Acceptance criteria:**
- [ ] Score is deterministic given same inputs
- [ ] Interest match contributes 5.0 per matching category
- [ ] Recency: <6h = +3.0, <24h = +1.5, >24h = +0.0
- [ ] Diversity: article_count * 0.5, capped at 3.0
- [ ] All tests from `test_personalization.py` pass

### T3.2: Story selection

**Task:** `select_stories()` picks the top-N stories for a user, excluding already-seen.

**Tests:**
```
test_select_excludes_seen_stories    — stories with engagement records are filtered out
test_select_respects_briefing_depth  — returns at most user.briefing_depth stories
test_select_returns_sorted           — highest-scored story is first
test_select_48h_window               — stories older than 48h are excluded
test_select_empty_when_no_stories    — no analyzed clusters → empty list
```

**Acceptance criteria:**
- [ ] Excludes stories the user has already engaged with
- [ ] Respects `user.briefing_depth` as the maximum count
- [ ] Only considers clusters from the last 48 hours
- [ ] Returns stories sorted by descending score

### T3.3: Briefing generation via Claude

**Task:** `generate_briefing()` produces attributed, formatted content.

**Tests:**
```
test_briefing_contains_all_stories     — mock Claude, verify all story headlines present
test_briefing_has_source_attribution   — output contains "(Source: ...)" for claims
test_briefing_respects_format          — EMAIL format includes HTML tags, AUDIO_SCRIPT does not
test_briefing_handles_empty_stories    — 0 stories returns early, no Claude call
```

**Acceptance criteria:**
- [ ] Every factual claim in the briefing is attributed to a named source
- [ ] EMAIL format contains valid HTML (`<h2>`, `<p>`, links)
- [ ] Briefing length is ~800 words for 10 stories (within 20% tolerance)

### T3.4: Email delivery via Resend

**Task:** `send_email()` delivers formatted briefings.

**Tests:**
```
test_send_email_calls_resend         — mock resend.Emails.send, verify called with correct args
test_send_email_subject_has_date     — subject line includes today's date
test_send_email_failure_logged       — Resend API error is logged, returns False
test_send_email_success_returns_true
```

**Acceptance criteria:**
- [ ] Email sent via Resend API with `from`, `to`, `subject`, `html` fields
- [ ] Subject: "Your News Briefing — May 18, 2026" (dynamic date)
- [ ] API errors are caught, logged, and return `False` (no crash)
- [ ] One integration test with real Resend API key (marked `@pytest.mark.integration`)

### T3.5: Briefing storage and tracking

**Task:** `create_and_send()` persists the briefing and delivery status.

**Tests:**
```
test_briefing_stored_in_db           — Briefing row created with content and story_count
test_briefing_marked_sent            — sent=True and sent_at populated after successful send
test_briefing_not_marked_sent        — sent=False if email delivery fails
test_briefing_skipped_no_stories     — no Briefing row created if story list is empty
```

**Acceptance criteria:**
- [ ] Briefing row persisted before send attempt
- [ ] `sent` and `sent_at` updated only on successful delivery
- [ ] `story_count` matches actual number of stories included
- [ ] Empty story list short-circuits (no Claude call, no DB row)

---

## M4 — End-to-End Loop

### T4.1: Scheduler orchestration

**Task:** `main.py` runs all cycles on correct schedules. Agents communicate via DB status fields, not a message queue.

**Tests:**
```
test_scheduler_registers_all_jobs    — 3 jobs registered: discovery, analysis, briefing
test_scheduler_intervals_correct     — discovery=2h, analysis=30m, briefing=7AM cron
test_scheduler_shutdown_on_signal    — SIGINT triggers clean shutdown
```

**Acceptance criteria:**
- [ ] All agent cycles are scheduled
- [ ] Discovery: every `discovery_interval_hours` (default 2)
- [ ] Analysis: every 30 minutes (picks up `status=RAW` clusters)
- [ ] Briefing: daily at 7 AM (picks up `status=ANALYZED` clusters, personalizes, delivers)
- [ ] SIGINT/SIGTERM cause graceful shutdown
- [ ] No Redis dependency — agents find work by querying DB status columns

### T4.2: End-to-end integration test

**Task:** Full pipeline from discovery to email delivery with real APIs.

**Tests:**
```
test_e2e_single_briefing    — seed a user, run discovery → analysis → personalization → delivery
                              verify: clusters in DB, perspectives in DB, briefing sent
```

**Acceptance criteria:**
- [ ] Brave API returns real results
- [ ] Claude produces valid analysis and briefing
- [ ] Email arrives in test inbox
- [ ] Total cycle time < 5 minutes for 10 stories
- [ ] No unhandled exceptions in logs

---

## M5 — Hardening

### T5.1: Error recovery and retries

**Task:** Transient failures (API timeouts, rate limits) are retried with backoff.

**Tests:**
```
test_brave_retry_on_timeout      — first call times out, second succeeds
test_claude_retry_on_rate_limit  — 429 triggers exponential backoff, then succeeds
test_resend_retry_on_5xx         — server error retried once, then logged as failure
test_max_retries_respected       — after 3 failures, give up and log
```

**Acceptance criteria:**
- [ ] All external API calls (Brave, Claude, Resend) have retry with exponential backoff
- [ ] Max 3 retries per call
- [ ] Each retry is logged with attempt number
- [ ] After max retries, error is logged and the item is skipped (not crashed)

### T5.2: Monitoring and alerting

**Task:** Pipeline failures trigger ntfy.sh push notifications.

**Tests:**
```
test_alert_on_discovery_failure   — discovery cycle exception triggers ntfy push
test_alert_on_zero_clusters       — discovery returns 0 clusters triggers warning
test_alert_on_briefing_failure    — email delivery failure triggers ntfy push
```

**Acceptance criteria:**
- [ ] ntfy.sh integration sends push on: agent crash, 0 results, delivery failure
- [ ] Alert includes: which agent, error message, timestamp
- [ ] Does not alert on expected empty states (e.g., no new stories at 3 AM)

### T5.3: Prompt quality iteration

**Task:** Analysis and briefing prompts produce consistent, high-quality output.

**Tests:**
```
test_analysis_prompt_returns_valid_schema   — 10 real clusters produce valid JSON 10/10 times
test_briefing_prompt_has_attribution        — 10 briefings all contain source attribution
test_briefing_prompt_no_hallucination       — claims in briefing trace to source snippets
```

**Acceptance criteria:**
- [ ] Analysis prompt JSON parse success rate > 95% over 50 test runs
- [ ] Briefing attribution rate: 100% of claims have "(Source: ...)"
- [ ] Manual spot-check: 0 fabricated claims in 10 sample briefings
- [ ] Prompts are versioned (stored as constants with version comments)

---

## M6 — Beta Launch

### T6.1: Seed source registry

**Task:** Curate and load the initial source list with trust/bias labels.

**Tests:**
```
test_seed_loads_all_sources      — ≥20 sources in DB after seed
test_seed_covers_bias_spectrum   — at least 1 source per BiasLabel value
test_seed_all_have_rss           — every seeded source has rss_url populated
```

**Acceptance criteria:**
- [ ] 20-30 sources covering: wire services (Reuters, AP, AFP), left/center/right outlets
- [ ] Each has hand-assigned trust_score and bias_label
- [ ] All have working RSS URLs verified manually
- [ ] Seed script is idempotent

### T6.2: User onboarding

**Task:** New users can register with email + interest selection.

**Tests:**
```
test_register_user_creates_row       — email + interests → User row in DB
test_register_duplicate_email        — same email twice → error, not duplicate
test_register_validates_email        — invalid email format rejected
test_register_default_preferences    — new user gets format=EMAIL, depth=10, is_pro=False
```

**Acceptance criteria:**
- [ ] Registration script/endpoint accepts email + interest categories
- [ ] Duplicate email returns clear error
- [ ] User receives first briefing within 24 hours of registration
- [ ] Default preferences match CLAUDE.md free tier spec

### T6.3: Beta operation and feedback

**Task:** Onboard 10-20 test users and collect structured feedback.

**Tests:**
```
(manual) — send test briefings for 7 days, collect qualitative feedback
```

**Acceptance criteria:**
- [ ] 10+ users receiving daily briefings for 7+ consecutive days
- [ ] Zero missed briefings (100% delivery rate)
- [ ] Feedback collected on: relevance, quality, length, attribution clarity
- [ ] Bug list triaged: P0 (blocks usage) fixed before public launch

---

## Deprecated Datetime Notice

All model defaults must use `datetime.now(datetime.UTC)` instead of `datetime.utcnow()` (deprecated in Python 3.12+). Fix in T0.1 alongside DB initialization.
